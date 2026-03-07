# 作者: lxl
# 说明: REST 接口入口与权限/审计/AI 编排逻辑。
from datetime import timedelta
import json
import math
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import httpx

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from autotest.auth import issue_auth_token
from autotest.ai_generator import (
    generate_test_cases_by_ai,
    generate_test_cases_from_openapi_summary,
    validate_ai_connection,
)
from autotest.executor import (
    debug_scenario_step as executor_debug_scenario_step,
    execute_scenario,
    execute_test_case,
    preview_runtime_case,
    preview_scenario_steps,
    _case_to_dict,
)
from autotest.monitoring import deploy_monitor_platform
from autotest.models import (
    ApiModule,
    LoginAuditLog,
    MonitorMetricSnapshot,
    MonitorPlatform,
    OperationAuditLog,
    Project,
    ProjectEnvironment,
    RunHistory,
    ScenarioDataSet,
    ScenarioRunHistory,
    TestCase,
    TestScenario,
    UserProjectAccess,
)
from autotest.openapi_parser import load_openapi_document, summarize_openapi_document
from autotest.serializers import (
    ApiModuleSerializer,
    MonitorPlatformSerializer,
    ProjectEnvironmentSerializer,
    ProjectSerializer,
    RunHistorySerializer,
    ScenarioDataSetSerializer,
    ScenarioRunHistorySerializer,
    TestCaseSerializer,
    TestScenarioSerializer,
)


def _fmt_dt(value):
    if not value:
        return None
    try:
        return value.isoformat()
    except Exception:  # noqa: BLE001
        return None


def _httpx_error_detail(prefix: str, exc: httpx.HTTPStatusError) -> str:
    response = getattr(exc, "response", None)
    status_code = response.status_code if response is not None else "unknown"
    preview = ""
    if response is not None:
        try:
            raw = response.text or ""
            preview = str(raw).strip().replace("\n", " ").replace("\r", " ")
        except Exception:  # noqa: BLE001
            preview = ""
    if len(preview) > 220:
        preview = preview[:220] + "..."
    if preview:
        return f"{prefix}: {status_code}，响应片段: {preview}"
    return f"{prefix}: {status_code}"


def _request_ip(request) -> str:
    xff = str(request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return str(request.META.get("REMOTE_ADDR") or "").strip()


def _log_login_event(request, *, username: str, success: bool, detail: str = "", user=None):
    try:
        # 登录审计写入失败不能反向影响登录主流程。
        LoginAuditLog.objects.create(
            user=user if getattr(user, "id", None) else None,
            username=(username or "").strip() or None,
            success=1 if success else 0,
            detail=(detail or "").strip()[:255] or None,
            ip=_request_ip(request)[:64] or None,
            user_agent=str(request.META.get("HTTP_USER_AGENT") or "").strip()[:255] or None,
        )
    except Exception:
        # Audit logging should never block auth flow
        pass


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


def _user_payload(user):
    project_ids = []
    if _is_root_admin(user):
        project_ids = list(Project.objects.values_list("id", flat=True))
    elif user and getattr(user, "id", None):
        project_ids = list(
            UserProjectAccess.objects.filter(user_id=user.id, is_active=True).values_list("project_id", flat=True)
        )
    return {
        "id": int(user.id),
        "username": str(user.username or ""),
        "email": str(user.email or ""),
        "is_active": bool(user.is_active),
        "is_admin": True,
        "is_root_admin": _is_root_admin(user),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "project_ids": sorted(project_ids),
        "last_login": _fmt_dt(getattr(user, "last_login", None)),
        "date_joined": _fmt_dt(getattr(user, "date_joined", None)),
    }


def _ensure_default_admin_user():
    user_model = get_user_model()
    if user_model.objects.exists():
        return
    username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin").strip() or "admin"
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123456").strip() or "admin123456"
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "").strip()
    user_model.objects.create_superuser(username=username, password=password, email=email)


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login(request):
    _ensure_default_admin_user()
    username = str(request.data.get("username") or "").strip()
    password = str(request.data.get("password") or "")
    if not username or not password:
        _log_login_event(request, username=username, success=False, detail="empty_credentials")
        return Response({"detail": "用户名和密码不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=username, password=password)
    if user is None:
        _log_login_event(request, username=username, success=False, detail="invalid_credentials")
        return Response({"detail": "用户名或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        _log_login_event(request, username=username, success=False, detail="user_disabled", user=user)
        return Response({"detail": "账号已禁用"}, status=status.HTTP_403_FORBIDDEN)
    token = issue_auth_token(user)
    _log_login_event(request, username=username, success=True, detail="login_success", user=user)
    return Response({"token": token, "user": _user_payload(user)})


@api_view(["GET"])
def auth_me(request):
    return Response(_user_payload(request.user))


@api_view(["POST"])
def auth_logout(request):
    return Response({"ok": True})


@api_view(["POST"])
def auth_change_password(request):
    current_password = str(request.data.get("current_password") or "")
    new_password = str(request.data.get("new_password") or "")
    if not current_password or not new_password:
        return Response({"detail": "当前密码和新密码不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    if len(new_password) < 6:
        return Response({"detail": "新密码长度至少6位"}, status=status.HTTP_400_BAD_REQUEST)
    user = request.user
    if not user.check_password(current_password):
        return Response({"detail": "当前密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"ok": True})


@api_view(["GET", "POST"])
def auth_user_list_create(request):
    if not _is_root_admin(request.user):
        return Response({"detail": "仅 admin 可管理用户"}, status=status.HTTP_403_FORBIDDEN)
    user_model = get_user_model()
    if request.method == "GET":
        users = user_model.objects.all().order_by("id")
        return Response([_user_payload(item) for item in users])

    username = str(request.data.get("username") or "").strip()
    password = str(request.data.get("password") or "")
    if not username or not password:
        return Response({"detail": "用户名和密码不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    if user_model.objects.filter(username=username).exists():
        return Response({"detail": "用户名已存在"}, status=status.HTTP_400_BAD_REQUEST)
    email = str(request.data.get("email") or "").strip()
    is_active = bool(request.data.get("is_active", True))
    project_ids = request.data.get("project_ids")
    normalized_project_ids = []
    if isinstance(project_ids, list):
        for item in project_ids:
            try:
                pid = int(item)
            except (TypeError, ValueError):
                continue
            if pid > 0:
                normalized_project_ids.append(pid)
    user = user_model.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_active=is_active,
        is_staff=True,
        is_superuser=False,
    )
    if normalized_project_ids:
        valid_ids = list(Project.objects.filter(id__in=normalized_project_ids).values_list("id", flat=True))
        UserProjectAccess.objects.bulk_create(
            [
                UserProjectAccess(user_id=user.id, project_id=pid, is_active=True)
                for pid in valid_ids
            ],
            ignore_conflicts=True,
        )
    return Response(_user_payload(user), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def auth_user_detail(request, user_id: int):
    if not _is_root_admin(request.user):
        return Response({"detail": "仅 admin 可管理用户"}, status=status.HTTP_403_FORBIDDEN)
    user_model = get_user_model()
    user = get_object_or_404(user_model, id=user_id)

    if request.method == "DELETE":
        if int(request.user.id) == int(user.id):
            return Response({"detail": "不能删除当前登录账号"}, status=status.HTTP_400_BAD_REQUEST)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    email = str(request.data.get("email") or user.email or "").strip()
    is_active = request.data.get("is_active", user.is_active)
    user.email = email
    user.is_active = bool(is_active)
    reset_password = str(request.data.get("password") or "").strip()
    if reset_password:
        user.set_password(reset_password)
    if str(user.username or "").strip().lower() != "admin":
        user.is_staff = True
        user.is_superuser = False
    user.save()
    if "project_ids" in request.data:
        raw_ids = request.data.get("project_ids")
        normalized_project_ids = []
        if isinstance(raw_ids, list):
            for item in raw_ids:
                try:
                    pid = int(item)
                except (TypeError, ValueError):
                    continue
                if pid > 0:
                    normalized_project_ids.append(pid)
        valid_ids = list(Project.objects.filter(id__in=normalized_project_ids).values_list("id", flat=True))
        UserProjectAccess.objects.filter(user_id=user.id).exclude(project_id__in=valid_ids).delete()
        existing_ids = set(
            UserProjectAccess.objects.filter(user_id=user.id).values_list("project_id", flat=True)
        )
        UserProjectAccess.objects.bulk_create(
            [
                UserProjectAccess(user_id=user.id, project_id=pid, is_active=True)
                for pid in valid_ids
                if pid not in existing_ids
            ],
            ignore_conflicts=True,
        )
        UserProjectAccess.objects.filter(user_id=user.id, project_id__in=valid_ids).update(is_active=True)
    return Response(_user_payload(user))


def _ensure_default_project():
    project = Project.objects.order_by("id").first()
    if project:
        return project
    return Project.objects.create(name="默认项目", description="系统自动创建")


def _is_root_admin(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    username = str(getattr(user, "username", "") or "").strip().lower()
    return username == "admin" or bool(getattr(user, "is_superuser", False))


def _accessible_project_ids(user):
    # 超管可访问全部项目；普通用户按 UserProjectAccess 做白名单过滤。
    if _is_root_admin(user):
        return set(Project.objects.values_list("id", flat=True))
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        UserProjectAccess.objects.filter(user_id=user.id, is_active=True).values_list("project_id", flat=True)
    )


def _ensure_project_access(request, project_id):
    # 统一项目鉴权入口，避免每个视图重复写权限判断。
    try:
        pid = int(project_id)
    except (TypeError, ValueError):
        return None
    if pid in _accessible_project_ids(request.user):
        return pid
    return None


def _collect_module_ids_with_descendants(project_id: int, module_id: int):
    # BFS 收集当前模块及所有子模块，用于批量执行/批量查询。
    all_ids = set()
    queue = [int(module_id)]
    while queue:
        current = queue.pop(0)
        if current in all_ids:
            continue
        all_ids.add(current)
        children = list(
            ApiModule.objects.filter(project_id=project_id, parent_id=current).values_list("id", flat=True)
        )
        queue.extend(children)
    return list(all_ids)


def _ensure_admin_user(request):
    if not _is_root_admin(request.user):
        return Response({"detail": "仅 admin 可执行监控平台管理操作"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _as_bool(value, default=True):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _parse_int_param(value, default: int, minimum=None, maximum=None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _list_query_options(request, *, default_page_size: int = 20, max_page_size: int = 100) -> dict:
    keyword = str(request.GET.get("keyword") or request.GET.get("search") or "").strip()
    ordering = str(request.GET.get("ordering") or "").strip()
    has_page = request.GET.get("page") not in (None, "")
    has_page_size = request.GET.get("page_size") not in (None, "")
    paginate = has_page or has_page_size or bool(keyword) or bool(ordering)
    page = _parse_int_param(request.GET.get("page"), 1, minimum=1)
    page_size = _parse_int_param(request.GET.get("page_size"), default_page_size, minimum=1, maximum=max_page_size)
    return {
        "paginate": paginate,
        "page": page,
        "page_size": page_size,
        "keyword": keyword,
        "ordering": ordering,
    }


def _normalize_ordering(raw_value: str, allowed_fields: set[str], default: str) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return default
    field = raw[1:] if raw.startswith("-") else raw
    if field not in allowed_fields:
        return default
    return raw


def _paginated_response(queryset, serializer_class, *, page: int, page_size: int):
    total = queryset.count()
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    if total_pages > 0:
        page = min(max(1, page), total_pages)
    else:
        page = 1
    start = (page - 1) * page_size
    end = start + page_size
    serializer = serializer_class(queryset[start:end], many=True)
    return Response(
        {
            "items": serializer.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }
    )


def _scenario_runtime_options_from_payload(payload) -> dict:
    return {
        "data_mode": payload.get("data_mode"),
        "data_pick": payload.get("data_pick"),
        "param_retry_count": payload.get("param_retry_count"),
        "param_enabled": payload.get("param_enabled"),
        "environment_id": payload.get("environment_id"),
    }


def _build_scenario_preview_runtime(request):
    payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    raw_id = payload.pop("scenario_id", None) or payload.pop("id", None)
    instance = None
    try:
        scenario_id = int(raw_id)
    except (TypeError, ValueError):
        scenario_id = 0
    if scenario_id > 0:
        instance = TestScenario.objects.filter(id=scenario_id).first()
    serializer = TestScenarioSerializer(instance=instance, data=payload)
    serializer.is_valid(raise_exception=True)
    validated = dict(serializer.validated_data)
    steps = list(validated.pop("steps", []) or [])
    scenario = TestScenario(**validated)
    return scenario, steps, _scenario_runtime_options_from_payload(request.data)


@api_view(["GET", "POST"])
def module_list_create(request):
    if request.method == "GET":
        project_id = request.GET.get("project_id")
        if not project_id:
            return Response([])
        pid = _ensure_project_access(request, project_id)
        if not pid:
            return Response([])
        queryset = ApiModule.objects.filter(project_id=pid).order_by("parent_id", "id")
        serializer = ApiModuleSerializer(queryset, many=True)
        return Response(serializer.data)

    payload = request.data.copy()
    if not payload.get("project"):
        return Response({"detail": "project 为必填项"}, status=status.HTTP_400_BAD_REQUEST)
    pid = _ensure_project_access(request, payload.get("project"))
    if not pid:
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    payload["project"] = pid
    serializer = ApiModuleSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def module_detail(request, module_id: int):
    module = get_object_or_404(ApiModule, id=module_id)
    if module.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response(ApiModuleSerializer(module).data)

    if request.method == "PUT":
        serializer = ApiModuleSerializer(module, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    if ApiModule.objects.filter(parent_id=module.id).exists():
        return Response({"detail": "该模块下仍有子模块，无法删除"}, status=status.HTTP_400_BAD_REQUEST)
    if TestCase.objects.filter(module_id=module.id).exists():
        return Response({"detail": "该模块下仍有关联接口，无法删除"}, status=status.HTTP_400_BAD_REQUEST)
    if TestScenario.objects.filter(module_id=module.id).exists():
        return Response({"detail": "该模块下仍有关联场景，无法删除"}, status=status.HTTP_400_BAD_REQUEST)
    if ScenarioDataSet.objects.filter(module_id=module.id).exists():
        return Response({"detail": "该模块下仍有关联数据集，无法删除"}, status=status.HTTP_400_BAD_REQUEST)
    module.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
def project_list_create(request):
    if request.method == "GET":
        project_ids = _accessible_project_ids(request.user)
        queryset = Project.objects.filter(id__in=project_ids)
        serializer = ProjectSerializer(queryset, many=True)
        return Response(serializer.data)

    serializer = ProjectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    project = serializer.save()
    if not _is_root_admin(request.user):
        UserProjectAccess.objects.update_or_create(
            user_id=request.user.id,
            project_id=project.id,
            defaults={"is_active": True},
        )
    return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def project_detail(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)
    if project.id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response(ProjectSerializer(project).data)

    if request.method == "PUT":
        serializer = ProjectSerializer(project, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(ProjectSerializer(updated).data)

    if TestCase.objects.filter(project_id=project.id).exists():
        return Response(
            {"detail": "该项目下仍有关联接口，无法删除"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    project.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
def data_set_list_create(request):
    if request.method == "GET":
        project_id = request.GET.get("project_id")
        queryset = ScenarioDataSet.objects.select_related("project", "module").all()
        project_ids = _accessible_project_ids(request.user)
        queryset = queryset.filter(project_id__in=project_ids)
        if project_id:
            pid = _ensure_project_access(request, project_id)
            if not pid:
                return Response([])
            queryset = queryset.filter(project_id=pid)
        serializer = ScenarioDataSetSerializer(queryset.order_by("-id")[:200], many=True)
        return Response(serializer.data)

    payload = request.data.copy()
    if not payload.get("project"):
        return Response({"detail": "project 为必填项"}, status=status.HTTP_400_BAD_REQUEST)
    pid = _ensure_project_access(request, payload.get("project"))
    if not pid:
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    payload["project"] = pid
    serializer = ScenarioDataSetSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def data_set_detail(request, data_set_id: int):
    data_set = get_object_or_404(ScenarioDataSet.objects.select_related("project", "module"), id=data_set_id)
    if data_set.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response(ScenarioDataSetSerializer(data_set).data)

    if request.method == "PUT":
        serializer = ScenarioDataSetSerializer(data_set, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    TestScenario.objects.filter(data_set_id=data_set.id).update(
        data_set=None,
        param_enabled=False,
    )
    data_set.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
def test_case_list_create(request):
    if request.method == "GET":
        options = _list_query_options(request, default_page_size=20, max_page_size=200)
        queryset = TestCase.objects.select_related("project", "environment", "module").all()
        queryset = queryset.filter(project_id__in=_accessible_project_ids(request.user))
        project_id = request.GET.get("project_id")
        if not project_id:
            return Response([])
        pid = _ensure_project_access(request, project_id)
        if not pid:
            return Response([])
        queryset = queryset.filter(project_id=pid)
        module_id = request.GET.get("module_id")
        if module_id:
            try:
                module_id_num = int(module_id)
            except (TypeError, ValueError):
                return Response([])
            if module_id_num == -1:
                queryset = queryset.filter(module__isnull=True)
            else:
                module = get_object_or_404(ApiModule, id=module_id_num)
                if module.project_id not in _accessible_project_ids(request.user):
                    return Response([])
                descendant_ids = _collect_module_ids_with_descendants(module.project_id, module.id)
                queryset = queryset.filter(module_id__in=descendant_ids)
        keyword = options["keyword"]
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(path__icontains=keyword)
                | Q(base_url__icontains=keyword)
                | Q(description__icontains=keyword)
                | Q(method__icontains=keyword)
            )
        queryset = queryset.order_by(
            _normalize_ordering(
                options["ordering"],
                {"id", "name", "path", "method", "created_at", "updated_at"},
                "-updated_at",
            )
        )
        if options["paginate"]:
            return _paginated_response(
                queryset,
                TestCaseSerializer,
                page=options["page"],
                page_size=options["page_size"],
            )
        serializer = TestCaseSerializer(queryset, many=True)
        return Response(serializer.data)

    payload = request.data.copy()
    if not payload.get("project"):
        return Response({"detail": "project 为必填项"}, status=status.HTTP_400_BAD_REQUEST)
    pid = _ensure_project_access(request, payload.get("project"))
    if not pid:
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    payload["project"] = pid
    serializer = TestCaseSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def test_case_detail(request, case_id: int):
    case = get_object_or_404(TestCase.objects.select_related("project", "environment", "module"), id=case_id)
    if case.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(TestCaseSerializer(case).data)

    if request.method == "PUT":
        serializer = TestCaseSerializer(case, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    case.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def run_test_case(request, case_id: int):
    case = get_object_or_404(TestCase, id=case_id)
    if case.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    result = execute_test_case(case)
    payload = dict(result or {})
    if "request" in payload and "request_snapshot" not in payload:
        payload["request_snapshot"] = payload.pop("request")
    else:
        payload.pop("request", None)
    history = RunHistory.objects.create(test_case=case, **payload)
    return Response({"history": RunHistorySerializer(history).data})


@api_view(["POST"])
def preview_test_case_runtime(request):
    payload = request.data.copy()
    raw_id = payload.pop("case_id", None) or payload.pop("id", None)
    instance = None
    try:
        case_id = int(raw_id)
    except (TypeError, ValueError):
        case_id = 0
    if case_id > 0:
        instance = TestCase.objects.filter(id=case_id).first()
    if not payload.get("project"):
        return Response({"detail": "project 为必填项"}, status=status.HTTP_400_BAD_REQUEST)
    pid = _ensure_project_access(request, payload.get("project"))
    if not pid:
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    payload["project"] = pid
    serializer = TestCaseSerializer(instance=instance, data=payload)
    serializer.is_valid(raise_exception=True)
    preview_case = TestCase(**serializer.validated_data)
    return Response(preview_runtime_case(_case_to_dict(preview_case)))


@api_view(["GET"])
def run_history_list(request):
    options = _list_query_options(request, default_page_size=20, max_page_size=200)
    test_case_id = request.GET.get("test_case_id")
    project_id = request.GET.get("project_id")
    queryset = RunHistory.objects.select_related("test_case").filter(
        test_case__project_id__in=_accessible_project_ids(request.user)
    )
    if test_case_id:
        queryset = queryset.filter(test_case_id=test_case_id)
    if project_id:
        pid = _ensure_project_access(request, project_id)
        if not pid:
            return Response([])
        queryset = queryset.filter(test_case__project_id=pid)
    keyword = options["keyword"]
    if keyword:
        queryset = queryset.filter(
            Q(test_case__name__icontains=keyword)
            | Q(error_message__icontains=keyword)
            | Q(assertion_result__icontains=keyword)
        )
    queryset = queryset.order_by(
        _normalize_ordering(
            options["ordering"],
            {"id", "created_at", "response_time_ms", "status_code", "success"},
            "-created_at",
        )
    )
    if options["paginate"]:
        return _paginated_response(
            queryset,
            RunHistorySerializer,
            page=options["page"],
            page_size=options["page_size"],
        )
    serializer = RunHistorySerializer(queryset[:100], many=True)
    return Response(serializer.data)


@api_view(["GET", "POST"])
def scenario_list_create(request):
    if request.method == "GET":
        options = _list_query_options(request, default_page_size=20, max_page_size=200)
        project_id = request.GET.get("project_id")
        module_id = request.GET.get("module_id")
        queryset = TestScenario.objects.select_related("project", "module", "data_set").prefetch_related("steps", "steps__test_case").all()
        queryset = queryset.filter(project_id__in=_accessible_project_ids(request.user))
        if project_id:
            pid = _ensure_project_access(request, project_id)
            if not pid:
                return Response([])
            queryset = queryset.filter(project_id=pid)
        if module_id:
            module = get_object_or_404(ApiModule, id=module_id)
            if module.project_id not in _accessible_project_ids(request.user):
                return Response([])
            descendant_ids = _collect_module_ids_with_descendants(module.project_id, module.id)
            queryset = queryset.filter(module_id__in=descendant_ids)
        keyword = options["keyword"]
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(description__icontains=keyword)
                | Q(module__name__icontains=keyword)
            )
        queryset = queryset.order_by(
            _normalize_ordering(
                options["ordering"],
                {"id", "name", "sort_order", "created_at", "updated_at", "module_id"},
                "sort_order",
            ),
            "id",
        )
        if options["paginate"]:
            return _paginated_response(
                queryset,
                TestScenarioSerializer,
                page=options["page"],
                page_size=options["page_size"],
            )
        serializer = TestScenarioSerializer(queryset, many=True)
        return Response(serializer.data)

    module_id = request.data.get("module")
    module = get_object_or_404(ApiModule, id=module_id) if module_id else None
    if not module:
        return Response({"detail": "场景必须关联模块"}, status=status.HTTP_400_BAD_REQUEST)
    if module.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    serializer = TestScenarioSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def scenario_detail(request, scenario_id: int):
    scenario = get_object_or_404(
        TestScenario.objects.select_related("module", "data_set").prefetch_related("steps", "steps__test_case"),
        id=scenario_id
    )
    if scenario.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response(TestScenarioSerializer(scenario).data)

    if request.method == "PUT":
        serializer = TestScenarioSerializer(scenario, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    scenario.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def preview_scenario_runtime(request):
    try:
        scenario, steps, runtime_options = _build_scenario_preview_runtime(request)
        return Response(preview_scenario_steps(scenario, steps, runtime_options=runtime_options))
    except IndexError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        if hasattr(exc, "detail"):
            raise
        return Response({"detail": f"场景预检失败: {exc}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def debug_scenario_step_runtime(request):
    raw_index = request.data.get("step_index")
    try:
        step_index = int(raw_index)
    except (TypeError, ValueError):
        return Response({"detail": "step_index 必须是整数"}, status=status.HTTP_400_BAD_REQUEST)
    include_previous = _as_bool(request.data.get("include_previous"), True)
    try:
        scenario, steps, runtime_options = _build_scenario_preview_runtime(request)
        result = executor_debug_scenario_step(
            scenario,
            steps,
            step_index=step_index,
            runtime_options=runtime_options,
            include_previous=include_previous,
        )
        return Response(result)
    except IndexError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        if hasattr(exc, "detail"):
            raise
        return Response({"detail": f"步骤调试失败: {exc}"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def run_scenario(request, scenario_id: int):
    scenario = get_object_or_404(
        TestScenario.objects.select_related("project", "module", "data_set").prefetch_related("steps", "steps__test_case"), id=scenario_id
    )
    if scenario.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    runtime_options = {
        "data_mode": request.data.get("data_mode"),
        "data_pick": request.data.get("data_pick"),
        "param_retry_count": request.data.get("param_retry_count"),
        "param_enabled": request.data.get("param_enabled"),
        "environment_id": request.data.get("environment_id"),
    }
    result = execute_scenario(scenario, runtime_options=runtime_options)
    history = ScenarioRunHistory.objects.create(scenario=scenario, **result)
    return Response({"history": ScenarioRunHistorySerializer(history).data})


def _run_scenarios_as_single_report(scenarios, report_name: str, runtime_options=None):
    # 将多个场景合并为一份执行报告，便于模块级和批量场景统一展示。
    shared_context = {}
    merged_results = []
    merged_iterations = []
    pass_count = 0
    fail_count = 0
    duration_ms = 0
    errors = []
    scenario_list = list(scenarios or [])
    if not scenario_list:
        return None, 0, 0

    for scenario in scenario_list:
        result = execute_scenario(scenario, initial_context=shared_context, runtime_options=runtime_options)
        if isinstance(result.get("context_snapshot"), dict):
            shared_context.update(result.get("context_snapshot") or {})
        if result.get("success"):
            pass_count += 1
        else:
            fail_count += 1
        duration_ms += int(result.get("duration_ms") or 0)
        if result.get("error_message"):
            errors.append(f"{scenario.name}: {result.get('error_message')}")
        for iteration in result.get("iterations") or []:
            if not isinstance(iteration, dict):
                continue
            item = dict(iteration)
            item["scenario_id"] = scenario.id
            item["scenario_name"] = scenario.name
            merged_iterations.append(item)

        for step in result.get("results") or []:
            item = dict(step)
            item["scenario_id"] = scenario.id
            item["scenario_name"] = scenario.name
            item["step_name"] = f"[{scenario.name}] {item.get('step_name') or ''}".strip()
            merged_results.append(item)

    snapshot = dict(shared_context)
    snapshot["__report_name"] = report_name
    snapshot["__scenario_count"] = len(scenario_list)
    merged_payload = {
        "success": 1 if fail_count == 0 else 0,
        "duration_ms": duration_ms,
        "results": merged_results,
        "iterations": merged_iterations,
        "context_snapshot": snapshot,
        "error_message": " | ".join(errors)[:255] if errors else None,
    }
    history = ScenarioRunHistory.objects.create(scenario=scenario_list[0], **merged_payload)
    return history, pass_count, fail_count


def _preview_scenarios_batch(scenarios, report_name: str, runtime_options=None):
    scenario_list = list(scenarios or [])
    if not scenario_list:
        return {
            "summary": {
                "report_name": report_name,
                "scenario_count": 0,
                "step_count": 0,
                "message": "批量预检不模拟真实响应，因此不会串联前序场景的响应提取变量。",
            },
            "scenarios": [],
        }

    previews = []
    total_steps = 0
    for scenario in scenario_list:
        step_list = list(scenario.steps.all())
        preview = preview_scenario_steps(scenario, step_list, runtime_options=runtime_options)
        steps = preview.get("steps") if isinstance(preview.get("steps"), list) else []
        total_steps += len(steps)
        previews.append(
            {
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "module_id": scenario.module_id,
                "module_name": getattr(getattr(scenario, "module", None), "name", "") or "",
                "summary": preview.get("summary") if isinstance(preview.get("summary"), dict) else {},
                "steps": steps,
            }
        )
    return {
        "summary": {
            "report_name": report_name,
            "scenario_count": len(scenario_list),
            "step_count": total_steps,
            "message": "批量预检不模拟真实响应，因此不会串联前序场景的响应提取变量。",
        },
        "scenarios": previews,
    }


@api_view(["POST"])
def run_module_scenarios(request, module_id: int):
    module = get_object_or_404(ApiModule, id=module_id)
    if module.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    descendant_ids = _collect_module_ids_with_descendants(module.project_id, module.id)
    scenarios = (
        TestScenario.objects.filter(module_id__in=descendant_ids)
        .select_related("data_set")
        .prefetch_related("steps", "steps__test_case")
        .order_by("sort_order", "id")
    )
    scenario_list = list(scenarios)
    report_name = f"模块批量执行（{len(scenario_list)}个场景）"
    runtime_options = {
        "data_mode": request.data.get("data_mode"),
        "data_pick": request.data.get("data_pick"),
        "param_retry_count": request.data.get("param_retry_count"),
        "param_enabled": request.data.get("param_enabled"),
        "environment_id": request.data.get("environment_id"),
    }
    history, pass_count, fail_count = _run_scenarios_as_single_report(scenario_list, report_name, runtime_options=runtime_options)
    histories = [history] if history else []
    return Response(
        {
            "module": ApiModuleSerializer(module).data,
            "module_ids": descendant_ids,
            "scenario_count": len(scenario_list),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "histories": ScenarioRunHistorySerializer(histories, many=True).data,
        }
    )


@api_view(["POST"])
def preview_scenarios_batch(request):
    ordered_ids = request.data.get("ordered_ids")
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return Response({"detail": "ordered_ids 为必填数组"}, status=status.HTTP_400_BAD_REQUEST)

    normalized_ids = []
    for item in ordered_ids:
        try:
            scenario_id = int(item)
        except (TypeError, ValueError):
            continue
        if scenario_id > 0:
            normalized_ids.append(scenario_id)
    if not normalized_ids:
        return Response({"detail": "ordered_ids 无有效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    queryset = TestScenario.objects.filter(id__in=normalized_ids, project_id__in=_accessible_project_ids(request.user)).select_related("project", "data_set", "module").prefetch_related("steps", "steps__test_case")
    scenario_map = {item.id: item for item in queryset}
    if len(scenario_map) != len(set(normalized_ids)):
        return Response({"detail": "存在无效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    ordered_scenarios = [scenario_map[sid] for sid in normalized_ids if sid in scenario_map]
    report_name = f"批量预检（{len(ordered_scenarios)}个场景）"
    runtime_options = _scenario_runtime_options_from_payload(request.data)
    return Response(_preview_scenarios_batch(ordered_scenarios, report_name, runtime_options=runtime_options))


@api_view(["POST"])
def run_scenarios_batch(request):
    ordered_ids = request.data.get("ordered_ids")
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return Response({"detail": "ordered_ids 为必填数组"}, status=status.HTTP_400_BAD_REQUEST)

    normalized_ids = []
    for item in ordered_ids:
        try:
            scenario_id = int(item)
        except (TypeError, ValueError):
            continue
        if scenario_id > 0:
            normalized_ids.append(scenario_id)
    if not normalized_ids:
        return Response({"detail": "ordered_ids 无有效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    queryset = TestScenario.objects.filter(id__in=normalized_ids, module__project_id__in=_accessible_project_ids(request.user)).select_related("data_set", "module").prefetch_related("steps", "steps__test_case")
    scenario_map = {item.id: item for item in queryset}
    if len(scenario_map) != len(set(normalized_ids)):
        return Response({"detail": "存在无效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    ordered_scenarios = [scenario_map[sid] for sid in normalized_ids if sid in scenario_map]
    report_name = f"批量执行（{len(ordered_scenarios)}个场景）"
    runtime_options = {
        "data_mode": request.data.get("data_mode"),
        "data_pick": request.data.get("data_pick"),
        "param_retry_count": request.data.get("param_retry_count"),
        "param_enabled": request.data.get("param_enabled"),
        "environment_id": request.data.get("environment_id"),
    }
    history, pass_count, fail_count = _run_scenarios_as_single_report(ordered_scenarios, report_name, runtime_options=runtime_options)
    histories = [history] if history else []
    return Response(
        {
            "scenario_count": len(ordered_scenarios),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "histories": ScenarioRunHistorySerializer(histories, many=True).data,
        }
    )


@api_view(["POST"])
def scenario_reorder(request):
    ordered_ids = request.data.get("ordered_ids")
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return Response({"detail": "ordered_ids 为必填数组"}, status=status.HTTP_400_BAD_REQUEST)

    normalized = []
    for item in ordered_ids:
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    if not normalized:
        return Response({"detail": "ordered_ids 无有效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    scenarios = list(
        TestScenario.objects.filter(id__in=normalized, module__project_id__in=_accessible_project_ids(request.user))
        .select_related("module")
    )
    scenario_by_id = {item.id: item for item in scenarios}
    if len(scenario_by_id) != len(set(normalized)):
        return Response({"detail": "存在无效场景ID"}, status=status.HTTP_400_BAD_REQUEST)

    module_ids = {item.module_id for item in scenarios}
    if len(module_ids) > 1:
        return Response({"detail": "仅支持同一模块下场景排序"}, status=status.HTTP_400_BAD_REQUEST)

    for index, scenario_id in enumerate(normalized, start=1):
        item = scenario_by_id.get(scenario_id)
        if not item:
            continue
        item.sort_order = index
        item.save(update_fields=["sort_order", "updated_at"])
    return Response({"updated": len(normalized)})


@api_view(["GET"])
def scenario_run_history_list(request):
    options = _list_query_options(request, default_page_size=20, max_page_size=200)
    scenario_id = request.GET.get("scenario_id")
    project_id = request.GET.get("project_id")
    module_id = request.GET.get("module_id")
    queryset = ScenarioRunHistory.objects.select_related("scenario", "scenario__module").filter(
        scenario__project_id__in=_accessible_project_ids(request.user)
    )
    if scenario_id:
        queryset = queryset.filter(scenario_id=scenario_id)
    if project_id:
        pid = _ensure_project_access(request, project_id)
        if not pid:
            return Response([])
        queryset = queryset.filter(scenario__project_id=pid)
    if module_id:
        module = get_object_or_404(ApiModule, id=module_id)
        if module.project_id not in _accessible_project_ids(request.user):
            return Response([])
        descendant_ids = _collect_module_ids_with_descendants(module.project_id, module.id)
        queryset = queryset.filter(scenario__module_id__in=descendant_ids)
    keyword = options["keyword"]
    if keyword:
        queryset = queryset.filter(
            Q(scenario__name__icontains=keyword)
            | Q(error_message__icontains=keyword)
        )
    queryset = queryset.order_by(
        _normalize_ordering(
            options["ordering"],
            {"id", "created_at", "duration_ms", "success"},
            "-created_at",
        )
    )
    if options["paginate"]:
        return _paginated_response(
            queryset,
            ScenarioRunHistorySerializer,
            page=options["page"],
            page_size=options["page_size"],
        )
    serializer = ScenarioRunHistorySerializer(queryset[:100], many=True)
    return Response(serializer.data)


@api_view(["DELETE"])
def scenario_run_history_detail(request, history_id: int):
    history = get_object_or_404(ScenarioRunHistory, id=history_id)
    scenario = getattr(history, "scenario", None)
    module = getattr(scenario, "module", None)
    if not module or module.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    history.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["DELETE"])
def scenario_run_history_batch_delete(request):
    ids = request.data.get("ids")
    if not isinstance(ids, list) or not ids:
        return Response({"detail": "ids is required"}, status=status.HTTP_400_BAD_REQUEST)

    normalized_ids = []
    for item in ids:
        try:
            normalized_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    if not normalized_ids:
        return Response({"detail": "valid ids is required"}, status=status.HTTP_400_BAD_REQUEST)

    queryset = ScenarioRunHistory.objects.filter(
        id__in=normalized_ids,
        scenario__module__project_id__in=_accessible_project_ids(request.user),
    )
    deleted_count = queryset.count()
    queryset.delete()
    return Response({"deleted": deleted_count})


@api_view(["GET"])
def dashboard_summary(request):
    project_id = request.GET.get("project_id")
    project = None
    if project_id:
        try:
            project = Project.objects.filter(id=int(project_id)).first()
        except (TypeError, ValueError):
            project = None
        if project and project.id not in _accessible_project_ids(request.user):
            project = None

    case_queryset = TestCase.objects.all()
    case_queryset = case_queryset.filter(project_id__in=_accessible_project_ids(request.user))
    if project:
        case_queryset = case_queryset.filter(project_id=project.id)

    case_count = case_queryset.count()
    scenario_count_qs = TestScenario.objects.filter(module__project_id__in=_accessible_project_ids(request.user))
    if project:
        scenario_count_qs = scenario_count_qs.filter(module__project_id=project.id)
    scenario_count = scenario_count_qs.count()

    case_runs = RunHistory.objects.select_related("test_case").all()
    if project:
        case_runs = case_runs.filter(test_case__project_id=project.id)
    scenario_runs = ScenarioRunHistory.objects.select_related("scenario", "scenario__module").filter(
        scenario__module__project_id__in=_accessible_project_ids(request.user)
    )
    if project:
        scenario_runs = scenario_runs.filter(scenario__module__project_id=project.id)

    case_run_count = case_runs.count()
    scenario_run_count = scenario_runs.count()
    pass_count = case_runs.filter(success=1).count() + scenario_runs.filter(success=1).count()
    fail_count = (case_run_count + scenario_run_count) - pass_count

    case_latency_values = [
        int(v)
        for v in case_runs.exclude(response_time_ms__isnull=True).values_list(
            "response_time_ms", flat=True
        )[:200]
        if isinstance(v, int)
    ]
    scenario_latency_values = [
        int(v)
        for v in scenario_runs.exclude(duration_ms__isnull=True).values_list("duration_ms", flat=True)[:200]
        if isinstance(v, int)
    ]
    all_latency_values = case_latency_values + scenario_latency_values
    avg_latency_ms = (
        round(sum(all_latency_values) / len(all_latency_values)) if all_latency_values else 0
    )

    recent_case_runs = [
        {
            "id": h.id,
            "kind": "case",
            "name": h.test_case.name if h.test_case_id else f"Case #{h.test_case_id}",
            "success": bool(h.success),
            "status_code": h.status_code,
            "duration_ms": h.response_time_ms,
            "created_at": _fmt_dt(h.created_at),
        }
        for h in case_runs[:8]
    ]
    recent_scenario_runs = [
        {
            "id": h.id,
            "kind": "scenario",
            "name": h.scenario.name if h.scenario_id else f"Scenario #{h.scenario_id}",
            "success": bool(h.success),
            "status_code": None,
            "duration_ms": h.duration_ms,
            "created_at": _fmt_dt(h.created_at),
        }
        for h in scenario_runs[:8]
    ]
    recent_runs = sorted(
        recent_case_runs + recent_scenario_runs,
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )[:10]

    trend_days = []
    today = timezone.now().date()
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        case_day = case_runs.filter(created_at__date=day)
        scenario_day = scenario_runs.filter(created_at__date=day)
        total_runs = case_day.count() + scenario_day.count()
        pass_runs = case_day.filter(success=1).count() + scenario_day.filter(success=1).count()
        fail_runs = total_runs - pass_runs
        day_latencies = [
            int(v)
            for v in case_day.exclude(response_time_ms__isnull=True).values_list(
                "response_time_ms", flat=True
            )[:100]
            if isinstance(v, int)
        ]
        trend_days.append(
            {
                "date": day.isoformat(),
                "runs": total_runs,
                "pass": pass_runs,
                "fail": fail_runs,
                "avg_latency_ms": round(sum(day_latencies) / len(day_latencies))
                if day_latencies
                else 0,
            }
        )

    trend_total_runs = sum(item["runs"] for item in trend_days)
    trend_total_pass = sum(item["pass"] for item in trend_days)
    pass_rate_7d = round((trend_total_pass / trend_total_runs) * 100, 2) if trend_total_runs else 0

    latest_failures = [
        {
            "id": h.id,
            "kind": "case",
            "name": h.test_case.name if h.test_case_id else f"Case #{h.test_case_id}",
            "error_message": h.error_message or h.assertion_result or "",
            "created_at": _fmt_dt(h.created_at),
        }
        for h in case_runs.filter(success=0)[:5]
    ]
    latest_failures.extend(
        [
            {
                "id": h.id,
                "kind": "scenario",
                "name": h.scenario.name if h.scenario_id else f"Scenario #{h.scenario_id}",
                "error_message": h.error_message or "",
                "created_at": _fmt_dt(h.created_at),
            }
            for h in scenario_runs.filter(success=0)[:5]
        ]
    )
    latest_failures = sorted(
        latest_failures, key=lambda item: item.get("created_at") or "", reverse=True
    )[:5]

    slow_cases = [
        {
            "test_case_id": row["test_case_id"],
            "name": TestCase.objects.filter(id=row["test_case_id"]).values_list("name", flat=True).first()
            or f"Case #{row['test_case_id']}",
            "latest_latency_ms": row["response_time_ms"] or 0,
            "created_at": _fmt_dt(row["created_at"]),
        }
        for row in case_runs.filter(response_time_ms__isnull=False)
        .values("test_case_id", "response_time_ms", "created_at")[:50]
    ]
    slow_cases = sorted(slow_cases, key=lambda x: x["latest_latency_ms"], reverse=True)[:5]

    today = timezone.now().date()
    today_case_qs = case_runs.filter(created_at__date=today)
    today_scenario_qs = scenario_runs.filter(created_at__date=today)
    today_run_count = today_case_qs.count() + today_scenario_qs.count()

    # Failure top services (derived from test_case.base_url host)
    service_fail_counter = {}
    for h in case_runs.filter(success=0)[:500]:
        base_url = (h.test_case.base_url if h.test_case_id else "") or ""
        host = urlparse(base_url).netloc or base_url or "unknown"
        service_fail_counter[host] = service_fail_counter.get(host, 0) + 1
    fail_top_services = [
        {"service": name, "fail_count": count}
        for name, count in sorted(service_fail_counter.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Failure top APIs
    api_fail_counter = {}
    api_name_map = {}
    for h in case_runs.filter(success=0)[:1000]:
        if not h.test_case_id:
            continue
        api_fail_counter[h.test_case_id] = api_fail_counter.get(h.test_case_id, 0) + 1
        api_name_map[h.test_case_id] = h.test_case.name
    fail_top_apis = [
        {"test_case_id": case_id, "name": api_name_map.get(case_id, f"Case #{case_id}"), "fail_count": count}
        for case_id, count in sorted(api_fail_counter.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Latency top APIs by average latency from recent histories
    api_latency_buckets = {}
    for h in case_runs.exclude(response_time_ms__isnull=True)[:1000]:
        if not h.test_case_id or not isinstance(h.response_time_ms, int):
            continue
        bucket = api_latency_buckets.setdefault(
            h.test_case_id, {"name": h.test_case.name, "sum": 0, "count": 0, "max": 0}
        )
        bucket["sum"] += h.response_time_ms
        bucket["count"] += 1
        bucket["max"] = max(bucket["max"], h.response_time_ms)
    latency_top_apis = []
    for case_id, bucket in api_latency_buckets.items():
        latency_top_apis.append(
            {
                "test_case_id": case_id,
                "name": bucket["name"],
                "avg_latency_ms": round(bucket["sum"] / bucket["count"]) if bucket["count"] else 0,
                "max_latency_ms": bucket["max"],
                "sample_count": bucket["count"],
            }
        )
    latency_top_apis = sorted(latency_top_apis, key=lambda x: x["avg_latency_ms"], reverse=True)[:5]

    # AI pending review queue from persisted test cases.
    # Current rule: any API case whose description contains "AI" is treated as AI-generated.
    ai_cases_qs = case_queryset.filter(description__icontains="AI").order_by("-updated_at", "-id")
    ai_pending_items = [
        {
            "id": c.id,
            "name": c.name,
            "status": "pending",
            "updated_at": _fmt_dt(c.updated_at),
        }
        for c in ai_cases_qs[:10]
    ]
    ai_pending_review = {
        "count": ai_cases_qs.count(),
        "items": ai_pending_items,
        "message": "",
    }

    return Response(
        {
            "meta": {
                "project_name": project.name if project else os.getenv("PROJECT_NAME", "默认项目"),
                "window_days": 7,
                "pass_rate_7d": pass_rate_7d,
            },
            "kpis": {
                "api_count": case_count,
                "scenario_count": scenario_count,
                "case_run_count": case_run_count,
                "scenario_run_count": scenario_run_count,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "avg_latency_ms": avg_latency_ms,
                "today_run_count": today_run_count,
            },
            "trend": trend_days,
            "recent_runs": recent_runs,
            "latest_failures": latest_failures,
            "slow_cases": slow_cases,
            "fail_top_services": fail_top_services,
            "fail_top_apis": fail_top_apis,
            "latency_top_apis": latency_top_apis,
            "ai_pending_review": ai_pending_review,
        }
    )


@api_view(["GET"])
def suite_list(request):
    scenarios = TestScenario.objects.prefetch_related("steps").filter(
        module__project_id__in=_accessible_project_ids(request.user)
    )[:100]
    items = []
    for sc in scenarios:
        items.append(
            {
                "id": sc.id,
                "name": sc.name,
                "description": sc.description or "",
                "scenario_count": 1,
                "step_count": sc.steps.count(),
                "stop_on_failure": sc.stop_on_failure,
                "updated_at": _fmt_dt(sc.updated_at),
                "status": "active",
            }
        )
    return Response(
        {
            "items": items,
            "summary": {
                "total": len(items),
                "active": len(items),
                "scheduled": 0,
                "message": "Current suite page is backed by scenario data until dedicated suite models are added.",
            },
        }
    )


@api_view(["GET", "POST"])
def environment_list(request):
    if request.method == "GET":
        project_id = request.GET.get("project_id")
        if not project_id:
            return Response({"items": [], "summary": {"total": 0, "message": "请先选择项目"}})
        pid = _ensure_project_access(request, project_id)
        if not pid:
            return Response({"items": [], "summary": {"total": 0, "message": "无项目访问权限"}})
        queryset = ProjectEnvironment.objects.filter(project_id=pid).order_by("-id")
        serializer = ProjectEnvironmentSerializer(queryset, many=True)
        items = serializer.data
        for item in items:
            item["variables_count"] = len(item.get("variables") or {})
        return Response(
            {
                "items": items,
                "summary": {
                    "total": len(items),
                    "message": "环境与变量均来自后端接口，变量请使用 &变量名 引用",
                },
            }
        )

    payload = request.data.copy()
    if not payload.get("project"):
        return Response({"detail": "project 为必填项"}, status=status.HTTP_400_BAD_REQUEST)
    pid = _ensure_project_access(request, payload.get("project"))
    if not pid:
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    project = get_object_or_404(Project, id=pid)
    payload["project"] = project.id
    payload["name"] = (payload.get("name") or "").strip() or project.name
    if not isinstance(payload.get("variables"), dict):
        payload["variables"] = {}
    if not isinstance(payload.get("default_headers"), dict):
        payload["default_headers"] = {}

    serializer = ProjectEnvironmentSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def environment_detail(request, env_id: int):
    env = get_object_or_404(ProjectEnvironment, id=env_id)
    if env.project_id not in _accessible_project_ids(request.user):
        return Response({"detail": "无项目访问权限"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response(ProjectEnvironmentSerializer(env).data)

    if request.method == "PUT":
        payload = request.data.copy()
        payload["project"] = env.project_id
        payload["name"] = (payload.get("name") or "").strip() or env.name
        if not isinstance(payload.get("variables"), dict):
            payload["variables"] = {}
        if not isinstance(payload.get("default_headers"), dict):
            payload["default_headers"] = {}
        serializer = ProjectEnvironmentSerializer(env, data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    TestCase.objects.filter(environment_id=env.id).update(environment=None)
    env.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
def monitor_platform_list_create(request):
    if request.method == "GET":
        queryset = MonitorPlatform.objects.select_related("created_by").prefetch_related("monitor_targets").all().order_by("-id")
        serializer = MonitorPlatformSerializer(queryset, many=True)
        return Response(serializer.data)

    forbidden = _ensure_admin_user(request)
    if forbidden:
        return forbidden

    serializer = MonitorPlatformSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    platform = serializer.save(created_by=request.user)
    auto_deploy = _as_bool(request.data.get("auto_deploy"), True)
    adopted_existing = False
    detected_components = {}
    if auto_deploy:
        adopted_existing, detected_components = _adopt_existing_monitoring_stack(platform, trigger="create")
        if not adopted_existing:
            deploy_monitor_platform(platform, trigger="create")
        platform.refresh_from_db()
    payload = MonitorPlatformSerializer(platform).data
    payload["adopted_existing"] = adopted_existing
    payload["detected_components"] = detected_components
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def monitor_platform_detail(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform.objects.prefetch_related("monitor_targets"), id=platform_id)

    if request.method == "GET":
        return Response(MonitorPlatformSerializer(platform).data)

    forbidden = _ensure_admin_user(request)
    if forbidden:
        return forbidden

    if request.method == "PUT":
        payload = request.data.copy()
        # 空密码表示保持不变，只有显式输入时才更新。
        if "ssh_password" in payload and str(payload.get("ssh_password") or "").strip() == "":
            payload.pop("ssh_password", None)
        serializer = MonitorPlatformSerializer(platform, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        platform.refresh_from_db()
        return Response(MonitorPlatformSerializer(platform).data)

    if platform.offline_package_path:
        try:
            path = Path(platform.offline_package_path)
            if path.exists():
                path.unlink()
            parent = path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception:
            pass
    platform.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def monitor_platform_deploy(request, platform_id: int):
    forbidden = _ensure_admin_user(request)
    if forbidden:
        return forbidden
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    mode = str(request.data.get("deploy_mode") or "").strip().lower()
    if mode in {MonitorPlatform.DEPLOY_MODE_ONLINE, MonitorPlatform.DEPLOY_MODE_OFFLINE}:
        platform.deploy_mode = mode
        platform.save(update_fields=["deploy_mode", "updated_at"])
    adopted_existing = False
    detected_components = {}
    if platform.deploy_mode == MonitorPlatform.DEPLOY_MODE_ONLINE:
        adopted_existing, detected_components = _adopt_existing_monitoring_stack(platform, trigger="manual")
    if not adopted_existing:
        deploy_monitor_platform(platform, trigger="manual")
    platform.refresh_from_db()
    payload = MonitorPlatformSerializer(platform).data
    payload["adopted_existing"] = adopted_existing
    payload["detected_components"] = detected_components
    return Response(payload)


@api_view(["POST"])
def monitor_platform_upload_package(request, platform_id: int):
    forbidden = _ensure_admin_user(request)
    if forbidden:
        return forbidden
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    upload_file = request.FILES.get("package")
    if not upload_file:
        return Response({"detail": "请上传离线包文件（字段名: package）"}, status=status.HTTP_400_BAD_REQUEST)

    base_dir = Path(__file__).resolve().parent.parent / "storage" / "monitor_packages" / str(platform.id)
    base_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{timezone.now().strftime('%Y%m%d%H%M%S')}_{upload_file.name}"
    target_path = base_dir / file_name

    with target_path.open("wb") as f:
        for chunk in upload_file.chunks():
            f.write(chunk)

    # 同一平台仅保留最新离线包，避免占用过多磁盘。
    for item in base_dir.iterdir():
        if item == target_path:
            continue
        if item.is_file():
            try:
                item.unlink()
            except Exception:
                pass
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    platform.offline_package_name = upload_file.name
    platform.offline_package_path = str(target_path)
    platform.deploy_mode = MonitorPlatform.DEPLOY_MODE_OFFLINE
    platform.save(update_fields=["offline_package_name", "offline_package_path", "deploy_mode", "updated_at"])

    auto_deploy = _as_bool(request.data.get("auto_deploy"), True)
    if auto_deploy:
        deploy_monitor_platform(platform, trigger="upload_package")
        platform.refresh_from_db()
    return Response(MonitorPlatformSerializer(platform).data)


@api_view(["GET"])
def monitor_platform_status(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    return Response(
        {
            "id": platform.id,
            "name": platform.name,
            "platform_type": platform.platform_type,
            "target_count": platform.monitor_targets.filter(enabled=True).count(),
            "status": platform.status,
            "deploy_mode": platform.deploy_mode,
            "prometheus_url": platform.prometheus_url,
            "grafana_url": platform.grafana_url,
            "alertmanager_url": platform.alertmanager_url,
            "last_error": platform.last_error,
            "last_deployed_at": _fmt_dt(platform.last_deployed_at),
        }
    )


@api_view(["GET"])
def monitor_platform_logs(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    logs = platform.deploy_logs if isinstance(platform.deploy_logs, list) else []
    return Response({"id": platform.id, "name": platform.name, "logs": logs[-200:]})


@api_view(["GET"])
def monitor_platform_targets(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        return Response({"detail": "平台尚未部署或无 Prometheus 地址"}, status=status.HTTP_400_BAD_REQUEST)

    target_host = str(request.GET.get("target_host") or "").strip()
    job_filter = str(request.GET.get("job") or "").strip()
    include_dropped = _as_bool(request.GET.get("include_dropped"), False)
    try:
        limit = int(request.GET.get("limit") or 500)
    except Exception:
        limit = 500
    limit = max(1, min(limit, 5000))

    payload = _prometheus_targets_for_platform(platform)
    data = payload.get("data") if isinstance(payload, dict) else {}
    active_targets = data.get("activeTargets") if isinstance(data, dict) else []
    dropped_targets = data.get("droppedTargets") if isinstance(data, dict) else []
    if not isinstance(active_targets, list):
        active_targets = []
    if not isinstance(dropped_targets, list):
        dropped_targets = []

    instance_re = _prometheus_instance_regex(platform, target_host)
    rows = []
    for item in active_targets:
        if not isinstance(item, dict):
            continue
        labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}
        discovered = item.get("discoveredLabels") if isinstance(item.get("discoveredLabels"), dict) else {}
        scrape_pool = str(item.get("scrapePool") or "")
        job = str(labels.get("job") or scrape_pool or "").strip()
        instance = str(labels.get("instance") or discovered.get("__address__") or "").strip()
        if job_filter and job != job_filter:
            continue
        if instance_re and instance and not re.match(rf"^{instance_re}$", instance):
            continue
        health_raw = str(item.get("health") or "").strip().lower()
        health = health_raw if health_raw in {"up", "down"} else "unknown"
        rows.append(
            {
                "job": job,
                "instance": instance,
                "health": health,
                "scrape_pool": scrape_pool,
                "scrape_url": str(item.get("scrapeUrl") or ""),
                "last_error": str(item.get("lastError") or ""),
                "last_scrape": item.get("lastScrape"),
                "labels": labels,
            }
        )

    rows.sort(key=lambda x: (0 if x.get("health") == "down" else 1, str(x.get("job") or ""), str(x.get("instance") or "")))
    rows = rows[:limit]

    summary = {"total": len(rows), "up": 0, "down": 0, "unknown": 0, "jobs": {}}
    for row in rows:
        health = str(row.get("health") or "unknown")
        if health not in {"up", "down", "unknown"}:
            health = "unknown"
        summary[health] += 1
        job = str(row.get("job") or "-")
        if job not in summary["jobs"]:
            summary["jobs"][job] = {"total": 0, "up": 0, "down": 0, "unknown": 0}
        summary["jobs"][job]["total"] += 1
        summary["jobs"][job][health] += 1

    response = {
        "platform_id": platform.id,
        "platform_name": platform.name,
        "prometheus_url": prom_url,
        "target_host": target_host,
        "job": job_filter or "",
        "summary": summary,
        "items": rows,
        "active_total_raw": len(active_targets),
        "dropped_total_raw": len(dropped_targets),
    }
    if include_dropped:
        response["dropped_items"] = dropped_targets[: min(limit, 300)]
    return Response(response)


def _append_monitor_log(platform: MonitorPlatform, message: str, level: str = "info") -> None:
    logs = platform.deploy_logs if isinstance(platform.deploy_logs, list) else []
    logs.append(
        {
            "time": timezone.now().isoformat(),
            "level": str(level or "info"),
            "message": str(message or ""),
        }
    )
    if len(logs) > 200:
        logs = logs[-200:]
    platform.deploy_logs = logs


def _detect_monitor_components(platform: MonitorPlatform):
    # 关键逻辑说明(lxl): 新平台接入前先探测目标机是否已有监控组件，
    # 避免重复安装并为“复用已有监控栈”提供判定依据。
    detected = {
        "docker_available": False,
        "prometheus": False,
        "alertmanager": False,
        "node_exporter": False,
        "cadvisor": False,
    }
    try:
        from autotest.monitoring import _run_remote, _ssh_connect
    except Exception:
        return detected

    try:
        client = _ssh_connect(platform)
    except Exception:
        return detected
    try:
        code, out, _err = _run_remote(client, "docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null || true", timeout=20)
        if code == 0:
            detected["docker_available"] = True
        lines = [str(line or "").strip().lower() for line in str(out or "").splitlines() if str(line or "").strip()]
        for line in lines:
            parts = line.split(" ", 1)
            name = parts[0] if parts else ""
            image = parts[1] if len(parts) > 1 else ""
            if "prometheus" in name or "prom/prometheus" in image:
                detected["prometheus"] = True
            if "alertmanager" in name or "prom/alertmanager" in image:
                detected["alertmanager"] = True
            if "node-exporter" in name or "node_exporter" in name or "node-exporter" in image:
                detected["node_exporter"] = True
            if "cadvisor" in name or "cadvisor" in image:
                detected["cadvisor"] = True

        if not detected["node_exporter"]:
            _c1, out1, _e1 = _run_remote(client, "pgrep -fa node_exporter || true", timeout=10)
            _c2, out2, _e2 = _run_remote(client, "systemctl is-active node_exporter 2>/dev/null || true", timeout=10)
            if str(out1 or "").strip() or str(out2 or "").strip() == "active":
                detected["node_exporter"] = True
    except Exception:
        return detected
    finally:
        try:
            client.close()
        except Exception:
            pass
    return detected


def _adopt_existing_monitoring_stack(platform: MonitorPlatform, trigger: str = "manual"):
    detected = _detect_monitor_components(platform)
    if not detected.get("prometheus"):
        return False, detected

    try:
        from autotest.monitoring import _render_prometheus_config, _run_as_root, _run_remote, _ssh_connect
    except Exception:
        return False, detected

    try:
        client = _ssh_connect(platform)
    except Exception:
        return False, detected

    try:
        code_cfg, out_cfg, _err_cfg = _run_remote(client, "test -f /opt/ai-monitor-stack/prometheus.yml && echo yes || echo no", timeout=10)
        has_managed_cfg = code_cfg == 0 and str(out_cfg or "").strip() == "yes"
        changed_config = False

        if has_managed_cfg:
            tmp_cfg = f"/tmp/ai-monitor-prometheus-{platform.id}.yml"
            cfg_text = _render_prometheus_config(platform)
            sftp = client.open_sftp()
            try:
                with sftp.open(tmp_cfg, "w") as f:
                    f.write(cfg_text)
            finally:
                sftp.close()

            cmd = (
                "set -e;"
                "PROM=$(docker ps --format '{{.Names}} {{.Image}}' | awk '$2 ~ /prom\\/prometheus/ {print $1; exit}');"
                "if [ -z \"$PROM\" ]; then exit 2; fi;"
                f"docker cp {tmp_cfg} \"$PROM\":/etc/prometheus/prometheus.yml;"
                "docker kill --signal=HUP \"$PROM\" >/dev/null 2>&1 || true;"
                f"rm -f {tmp_cfg};"
            )
            code, out, err = _run_as_root(client, platform, cmd, timeout=60)
            if code != 0:
                return False, detected
            changed_config = True
        else:
            cmd = (
                "set -e;"
                "PROM=$(docker ps --format '{{.Names}} {{.Image}}' | awk '$2 ~ /prom\\/prometheus/ {print $1; exit}');"
                "if [ -z \"$PROM\" ]; then exit 2; fi;"
                "docker kill --signal=HUP \"$PROM\" >/dev/null 2>&1 || true;"
            )
            code, out, err = _run_as_root(client, platform, cmd, timeout=30)
            if code != 0:
                return False, detected

        if (detected.get("node_exporter") is False) and (detected.get("cadvisor") is False):
            return False, detected

        platform.status = MonitorPlatform.STATUS_RUNNING
        platform.last_error = ""
        host = str(platform.host or "").strip()
        platform.prometheus_url = f"http://{host}:9090"
        platform.alertmanager_url = f"http://{host}:9093"
        platform.last_deployed_at = timezone.now()
        _append_monitor_log(
            platform,
            (
                f"检测到已安装监控组件（触发方式: {trigger}），已切换为复用模式并刷新 Prometheus 抓取配置"
                if changed_config
                else f"检测到已安装监控组件（触发方式: {trigger}），已切换为复用模式（保留现有 Prometheus 配置）"
            ),
            level="info",
        )
        platform.save(
            update_fields=[
                "status",
                "last_error",
                "prometheus_url",
                "alertmanager_url",
                "last_deployed_at",
                "deploy_logs",
                "updated_at",
            ]
        )
        return True, detected
    except Exception:
        return False, detected
    finally:
        try:
            client.close()
        except Exception:
            pass


def _prometheus_query(prometheus_url: str, query: str):
    url = f"{str(prometheus_url).rstrip('/')}/api/v1/query"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, params={"query": query})
        resp.raise_for_status()
        payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else {}
    result = data.get("result") if isinstance(data, dict) else []
    if not isinstance(result, list) or not result:
        return None
    first = result[0] if isinstance(result[0], dict) else {}
    value = first.get("value") if isinstance(first, dict) else None
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        return float(value[1])
    except Exception:
        return None


def _prometheus_query_vector(prometheus_url: str, query: str):
    url = f"{str(prometheus_url).rstrip('/')}/api/v1/query"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, params={"query": query})
        resp.raise_for_status()
        payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else {}
    result = data.get("result") if isinstance(data, dict) else []
    if not isinstance(result, list):
        return []
    rows = []
    for item in result:
        if not isinstance(item, dict):
            continue
        metric = item.get("metric") if isinstance(item.get("metric"), dict) else {}
        value = item.get("value")
        if not isinstance(value, list) or len(value) < 2:
            continue
        try:
            numeric = float(value[1])
        except Exception:
            continue
        rows.append({"metric": metric, "value": numeric})
    return rows


def _prometheus_targets(prometheus_url: str):
    url = f"{str(prometheus_url).rstrip('/')}/api/v1/targets"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    return payload if isinstance(payload, dict) else {}


def _prometheus_query_via_ssh(platform: MonitorPlatform, query: str):
    # 关键逻辑说明(lxl): 当业务机无法直连 Prometheus 端口时，回退到 SSH 在目标机本地查询。
    # 这样即使 9090 未对外开放，也能通过已配置的运维账号拉取指标数据。
    host = str(platform.host or "").strip()
    if not host or not platform.ssh_password:
        return None
    try:
        from autotest.monitoring import _run_remote, _ssh_connect
    except Exception:
        return None
    safe_query = quote_plus(str(query or ""))
    cmd = (
        "if command -v curl >/dev/null 2>&1; then "
        f"curl -fsS --max-time 8 'http://127.0.0.1:9090/api/v1/query?query={safe_query}'; "
        "elif command -v wget >/dev/null 2>&1; then "
        f"wget -qO- --timeout=8 'http://127.0.0.1:9090/api/v1/query?query={safe_query}'; "
        "else exit 127; fi"
    )
    try:
        client = _ssh_connect(platform)
    except Exception:
        return None
    try:
        code, out, _err = _run_remote(client, cmd, timeout=15)
        if code != 0 or not str(out or "").strip():
            return None
        payload = json.loads(out)
        data = payload.get("data") if isinstance(payload, dict) else {}
        result = data.get("result") if isinstance(data, dict) else []
        if not isinstance(result, list) or not result:
            return None
        first = result[0] if isinstance(result[0], dict) else {}
        value = first.get("value") if isinstance(first, dict) else None
        if not isinstance(value, list) or len(value) < 2:
            return None
        return float(value[1])
    except Exception:
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


def _prometheus_query_vector_via_ssh(platform: MonitorPlatform, query: str):
    host = str(platform.host or "").strip()
    if not host or not platform.ssh_password:
        return []
    try:
        from autotest.monitoring import _run_remote, _ssh_connect
    except Exception:
        return []
    safe_query = quote_plus(str(query or ""))
    cmd = (
        "if command -v curl >/dev/null 2>&1; then "
        f"curl -fsS --max-time 8 'http://127.0.0.1:9090/api/v1/query?query={safe_query}'; "
        "elif command -v wget >/dev/null 2>&1; then "
        f"wget -qO- --timeout=8 'http://127.0.0.1:9090/api/v1/query?query={safe_query}'; "
        "else exit 127; fi"
    )
    try:
        client = _ssh_connect(platform)
    except Exception:
        return []
    try:
        code, out, _err = _run_remote(client, cmd, timeout=15)
        if code != 0 or not str(out or "").strip():
            return []
        payload = json.loads(out)
        data = payload.get("data") if isinstance(payload, dict) else {}
        result = data.get("result") if isinstance(data, dict) else []
        if not isinstance(result, list):
            return []
        rows = []
        for item in result:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric") if isinstance(item.get("metric"), dict) else {}
            value = item.get("value")
            if not isinstance(value, list) or len(value) < 2:
                continue
            try:
                numeric = float(value[1])
            except Exception:
                continue
            rows.append({"metric": metric, "value": numeric})
        return rows
    except Exception:
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def _prometheus_targets_via_ssh(platform: MonitorPlatform):
    host = str(platform.host or "").strip()
    if not host or not platform.ssh_password:
        return {}
    try:
        from autotest.monitoring import _run_remote, _ssh_connect
    except Exception:
        return {}
    cmd = (
        "if command -v curl >/dev/null 2>&1; then "
        "curl -fsS --max-time 8 'http://127.0.0.1:9090/api/v1/targets'; "
        "elif command -v wget >/dev/null 2>&1; then "
        "wget -qO- --timeout=8 'http://127.0.0.1:9090/api/v1/targets'; "
        "else exit 127; fi"
    )
    try:
        client = _ssh_connect(platform)
    except Exception:
        return {}
    try:
        code, out, _err = _run_remote(client, cmd, timeout=15)
        if code != 0 or not str(out or "").strip():
            return {}
        payload = json.loads(out)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    finally:
        try:
            client.close()
        except Exception:
            pass


def _prometheus_query_for_platform(platform: MonitorPlatform, query: str):
    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        return None
    try:
        return _prometheus_query(prom_url, query)
    except Exception:
        return _prometheus_query_via_ssh(platform, query)


def _prometheus_query_vector_for_platform(platform: MonitorPlatform, query: str):
    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        return []
    try:
        return _prometheus_query_vector(prom_url, query)
    except Exception:
        return _prometheus_query_vector_via_ssh(platform, query)


def _prometheus_query_first(platform: MonitorPlatform, queries):
    for query in queries:
        if not str(query or "").strip():
            continue
        value = _prometheus_query_for_platform(platform, query)
        if value is not None:
            return value
    return None


def _prometheus_targets_for_platform(platform: MonitorPlatform):
    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        return {}
    try:
        return _prometheus_targets(prom_url)
    except Exception:
        return _prometheus_targets_via_ssh(platform)


def _collect_platform_target_hosts(platform: MonitorPlatform) -> list[str]:
    rows = platform.monitor_targets.filter(enabled=True).order_by("sort_order", "id")
    hosts = []
    host_seen = set()
    for row in rows:
        host = str(row.host or "").strip()
        if not host or host in host_seen:
            continue
        host_seen.add(host)
        hosts.append(host)
    if not hosts:
        fallback = str(platform.host or "").strip()
        if fallback:
            hosts.append(fallback)
    return hosts


def _prometheus_instance_regex(platform: MonitorPlatform, target_host: str = "") -> str:
    platform_type = str(platform.platform_type or "").strip().lower()
    platform_host = str(platform.host or "").strip()
    selected_host = str(target_host or "").strip()
    if selected_host:
        # 关键逻辑说明(lxl): 单机场景默认采集本地 docker 网络内 exporter（instance 可能是 node-exporter:9100），
        # 若用户仅选择了平台主机 IP，不强制 instance 过滤，避免把有效数据全部过滤掉。
        if platform_type == MonitorPlatform.PLATFORM_TYPE_SINGLE and selected_host == platform_host:
            return ""
        return f"{re.escape(selected_host)}(?::.*)?"
    if platform_type == MonitorPlatform.PLATFORM_TYPE_SINGLE:
        return ""
    hosts = _collect_platform_target_hosts(platform)
    if not hosts:
        return ""
    escaped_hosts = [re.escape(item) for item in hosts if str(item or "").strip()]
    if not escaped_hosts:
        return ""
    return "(?:" + "|".join(escaped_hosts) + ")(?::.*)?"


def _docker_running_count_via_ssh(platform: MonitorPlatform):
    host = str(platform.host or "").strip()
    if not host or not platform.ssh_password:
        return None
    try:
        from autotest.monitoring import _run_as_root, _ssh_connect
    except Exception:
        return None
    cmd = (
        "if command -v docker >/dev/null 2>&1; then docker ps -q 2>/dev/null | wc -l; "
        "elif command -v crictl >/dev/null 2>&1; then crictl ps -q 2>/dev/null | wc -l; "
        "else echo ''; fi"
    )
    try:
        client = _ssh_connect(platform)
    except Exception:
        return None
    try:
        code, out, _err = _run_as_root(client, platform, cmd, timeout=20)
        if code != 0:
            return None
        lines = [str(line or "").strip() for line in str(out or "").splitlines()]
        text = next((line for line in reversed(lines) if line), "")
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


def _safe_number(value):
    if value is None:
        return None
    try:
        num = float(value)
    except Exception:
        return None
    if not math.isfinite(num):
        return None
    return num


def _safe_round(value, ndigits=2):
    num = _safe_number(value)
    if num is None:
        return None
    return round(num, ndigits)


def _safe_int(value):
    num = _safe_number(value)
    if num is None:
        return None
    return int(num)


def _monitor_metrics_has_values(metrics: dict) -> bool:
    if not isinstance(metrics, dict):
        return False
    for value in metrics.values():
        if isinstance(value, list):
            if value:
                return True
            continue
        if value is not None:
            return True
    return False


def _monitor_metrics_cache_seconds() -> int:
    try:
        return max(0, int(os.getenv("MONITOR_METRICS_CACHE_SECONDS", "120")))
    except Exception:
        return 120


def _persist_monitor_metric_snapshot(platform: MonitorPlatform, metrics: dict, collected_at=None, scope_host: str = ""):
    if not isinstance(metrics, dict):
        return
    try:
        snapshot = MonitorMetricSnapshot.objects.create(
            platform=platform,
            metrics=metrics,
            scope_host=str(scope_host or "").strip(),
            collected_at=collected_at or timezone.now(),
        )
        # 关键逻辑说明(lxl): 每个平台仅保留最近 2000 条监控快照，避免无上限增长占满数据库。
        stale_qs = MonitorMetricSnapshot.objects.filter(platform_id=platform.id).order_by("-collected_at", "-id")[2000:]
        stale_ids = list(stale_qs.values_list("id", flat=True))
        if stale_ids:
            MonitorMetricSnapshot.objects.filter(id__in=stale_ids).delete()
        return snapshot
    except Exception:
        return None


@api_view(["GET"])
def monitor_platform_metrics_latest(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    target_host = str(request.GET.get("target_host") or "").strip()
    force_refresh = str(request.GET.get("refresh") or "").strip().lower() in ("true", "1", "yes")
    cache_seconds = _monitor_metrics_cache_seconds()

    # 非强制刷新时，优先读取 DB 中最新快照
    snapshot = None
    qs = MonitorMetricSnapshot.objects.filter(platform_id=platform.id)
    if target_host:
        qs = qs.filter(scope_host=target_host)
    else:
        qs = qs.filter(Q(scope_host="") | Q(scope_host__isnull=True))
    snapshot = qs.order_by("-collected_at", "-id").first()

    snapshot_metrics = snapshot.metrics if snapshot is not None and isinstance(snapshot.metrics, dict) else {}
    snapshot_age = None
    if snapshot is not None and snapshot.collected_at:
        snapshot_age = round((timezone.now() - snapshot.collected_at).total_seconds(), 1)
    snapshot_has_values = _monitor_metrics_has_values(snapshot_metrics)
    snapshot_is_fresh = snapshot_age is not None and snapshot_age <= cache_seconds

    # 有新鲜且非空快照则直接返回，避免每次页面切换都实时查询 Prometheus。
    if snapshot is not None and not force_refresh and snapshot_has_values and snapshot_is_fresh:
        return Response({
            "platform_id": platform.id,
            "platform_name": platform.name,
            "target_host": target_host or "",
            "collected_at": _fmt_dt(snapshot.collected_at),
            "metrics": snapshot_metrics,
            "snapshot_age_seconds": snapshot_age,
            "source": "snapshot",
        })

    # 无快照或强制刷新：回退到实时采集
    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        return Response({"detail": "平台尚未部署或无 Prometheus 地址"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        from autotest.metrics_collector import collect_metrics_for_platform
        metrics, collected_at = collect_metrics_for_platform(platform, target_host)
    except httpx.HTTPStatusError as exc:
        if snapshot is not None:
            return Response({
                "platform_id": platform.id,
                "platform_name": platform.name,
                "target_host": target_host or "",
                "collected_at": _fmt_dt(snapshot.collected_at),
                "metrics": snapshot_metrics,
                "snapshot_age_seconds": snapshot_age,
                "source": "snapshot_fallback",
                "warning": _httpx_error_detail("实时采集失败，已回退到最近一次快照", exc),
            })
        return Response({"detail": _httpx_error_detail("Prometheus 查询失败", exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as exc:  # noqa: BLE001
        if snapshot is not None:
            return Response({
                "platform_id": platform.id,
                "platform_name": platform.name,
                "target_host": target_host or "",
                "collected_at": _fmt_dt(snapshot.collected_at),
                "metrics": snapshot_metrics,
                "snapshot_age_seconds": snapshot_age,
                "source": "snapshot_fallback",
                "warning": f"实时采集失败，已回退到最近一次快照: {exc}",
            })
        return Response({"detail": f"Prometheus 查询失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    live_metrics = metrics if isinstance(metrics, dict) else {}
    live_has_values = _monitor_metrics_has_values(live_metrics)
    if not live_has_values and snapshot is not None and snapshot_has_values:
        return Response({
            "platform_id": platform.id,
            "platform_name": platform.name,
            "target_host": target_host or "",
            "collected_at": _fmt_dt(snapshot.collected_at),
            "metrics": snapshot_metrics,
            "snapshot_age_seconds": snapshot_age,
            "source": "snapshot_fallback",
            "warning": "实时采集未返回有效指标，已回退到最近一次快照",
        })

    return Response({
        "platform_id": platform.id,
        "platform_name": platform.name,
        "target_host": target_host or "",
        "collected_at": collected_at.isoformat(),
        "metrics": live_metrics,
        "snapshot_age_seconds": 0,
        "source": "live",
    })


@api_view(["GET"])
def monitor_platform_metrics_history(request, platform_id: int):
    platform = get_object_or_404(MonitorPlatform, id=platform_id)
    target_host = str(request.GET.get("target_host") or "").strip()
    try:
        limit = int(request.GET.get("limit") or 60)
    except Exception:
        limit = 60
    limit = max(1, min(limit, 500))
    try:
        range_minutes = int(request.GET.get("range_minutes") or 0)
    except Exception:
        range_minutes = 0
    range_minutes = max(0, min(range_minutes, 60 * 24 * 30))
    queryset = MonitorMetricSnapshot.objects.filter(platform_id=platform.id)
    if target_host:
        queryset = queryset.filter(scope_host=target_host)
    else:
        queryset = queryset.filter(Q(scope_host="") | Q(scope_host__isnull=True))
    if range_minutes > 0:
        since = timezone.now() - timedelta(minutes=range_minutes)
        queryset = queryset.filter(collected_at__gte=since)
    queryset = queryset.order_by("-collected_at", "-id")[:limit]
    rows = list(queryset)[::-1]
    items = []
    for row in rows:
        metrics = row.metrics if isinstance(row.metrics, dict) else {}
        items.append(
            {
                "id": row.id,
                "collected_at": _fmt_dt(row.collected_at),
                "metrics": metrics,
            }
        )
    return Response(
        {
            "platform_id": platform.id,
            "platform_name": platform.name,
            "target_host": target_host,
            "count": len(items),
            "items": items,
        }
    )


@api_view(["GET"])
def rbac_overview(request):
    if not _is_root_admin(request.user):
        return Response({"detail": "仅 admin 可访问"}, status=status.HTTP_403_FORBIDDEN)
    user_model = get_user_model()
    all_projects = list(Project.objects.all().order_by("id").values("id", "name"))
    members = []
    for user in user_model.objects.all().order_by("id"):
        if _is_root_admin(user):
            project_ids = [int(item["id"]) for item in all_projects]
        else:
            project_ids = list(
                UserProjectAccess.objects.filter(user_id=user.id, is_active=True).values_list("project_id", flat=True)
            )
        members.append(
            {
                "id": int(user.id),
                "username": str(user.username or ""),
                "email": str(user.email or ""),
                "is_active": bool(user.is_active),
                "project_ids": sorted(project_ids),
                "last_login": _fmt_dt(getattr(user, "last_login", None)),
                "date_joined": _fmt_dt(getattr(user, "date_joined", None)),
            }
        )
    recent_case_runs = RunHistory.objects.select_related("test_case").all()[:5]
    audits = [
        {
            "id": f"case-run-{h.id}",
            "action": "run_case",
            "operator": "system",
            "target": h.test_case.name if h.test_case_id else f"Case #{h.test_case_id}",
            "result": "success" if h.success else "failed",
            "time": _fmt_dt(h.created_at),
        }
        for h in recent_case_runs
    ]
    recent_scenario_runs = ScenarioRunHistory.objects.select_related("scenario").all()[:5]
    audits.extend(
        [
            {
                "id": f"scenario-run-{h.id}",
                "action": "run_scenario",
                "operator": "system",
                "target": h.scenario.name if h.scenario_id else f"Scenario #{h.scenario_id}",
                "result": "success" if h.success else "failed",
                "time": _fmt_dt(h.created_at),
            }
            for h in recent_scenario_runs
        ]
    )
    recent_login_logs = LoginAuditLog.objects.select_related("user").all()[:20]
    audits.extend(
        [
            {
                "id": f"login-{h.id}",
                "action": "login",
                "operator": str(h.username or (h.user.username if h.user_id else "") or "-"),
                "target": str(h.username or (h.user.username if h.user_id else "") or "-"),
                "result": "success" if h.success else "failed",
                "time": _fmt_dt(h.created_at),
                "detail": str(h.detail or ""),
            }
            for h in recent_login_logs
        ]
    )
    recent_operation_logs = OperationAuditLog.objects.select_related("user").all()[:50]
    audits.extend(
        [
            {
                "id": f"op-{h.id}",
                "action": str(h.method or "").upper() or "operate",
                "operator": str(h.username or (h.user.username if h.user_id else "") or "-"),
                "target": str(h.path or "-"),
                "result": "success" if h.success else "failed",
                "time": _fmt_dt(h.created_at),
                "detail": str(h.detail or ""),
            }
            for h in recent_operation_logs
        ]
    )
    audits = sorted(audits, key=lambda x: x.get("time") or "", reverse=True)[:30]

    return Response(
        {
            "members": members,
            "projects": all_projects,
            "audits": audits,
            "summary": {
                "member_count": len(members),
                "role_count": 0,
                "audit_count": len(audits),
                "message": "按项目分权：admin 可访问全部项目，其他用户仅可访问授权项目。",
            },
        }
    )


@api_view(["POST"])
def ai_generate_test_cases(request):
    prompt = (request.data.get("prompt") or "").strip()
    base_url_hint = (request.data.get("base_url_hint") or "").strip() or None
    ai_base_url = (request.data.get("ai_base_url") or "").strip() or None
    ai_api_key = (request.data.get("ai_api_key") or "").strip() or None
    ai_model = (request.data.get("ai_model") or "").strip() or None
    raw_timeout = request.data.get("ai_timeout_seconds")
    ai_timeout_seconds = None
    if raw_timeout not in (None, ""):
        try:
            ai_timeout_seconds = int(raw_timeout)
        except (TypeError, ValueError):
            return Response({"detail": "ai_timeout_seconds 必须是整数"}, status=status.HTTP_400_BAD_REQUEST)
        if ai_timeout_seconds <= 0 or ai_timeout_seconds > 300:
            return Response({"detail": "ai_timeout_seconds 取值范围为 1-300"}, status=status.HTTP_400_BAD_REQUEST)
    if not prompt:
        return Response({"detail": "prompt 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = generate_test_cases_by_ai(
            prompt,
            base_url_hint=base_url_hint,
            ai_base_url=ai_base_url,
            ai_api_key=ai_api_key,
            ai_model=ai_model,
            ai_timeout_seconds=ai_timeout_seconds,
        )
        return Response(result)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except httpx.HTTPStatusError as exc:  # type: ignore[name-defined]
        return Response(
            {"detail": _httpx_error_detail("AI 接口调用失败", exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"AI 生成失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _local_cases_from_openapi_summary(summary: dict):
    base_url = str(summary.get("base_url") or "").strip()
    operations = summary.get("operations") if isinstance(summary.get("operations"), list) else []
    cases = []
    for idx, op in enumerate(operations, start=1):
        if not isinstance(op, dict):
            continue
        method = str(op.get("method") or "GET").upper()
        path = str(op.get("path") or "/").strip() or "/"
        op_summary = str(op.get("summary") or "").strip()
        op_desc = str(op.get("description") or "").strip()
        name = op_summary or f"{method} {path}"

        params_obj = {}
        headers_obj = {}
        for p in op.get("parameters") or []:
            if not isinstance(p, dict):
                continue
            p_name = str(p.get("name") or "").strip()
            if not p_name:
                continue
            p_in = str(p.get("in") or "").strip().lower()
            p_val = p.get("example") if p.get("example") is not None else ""
            if p_in in {"query", "path"}:
                params_obj[p_name] = p_val
            elif p_in == "header":
                headers_obj[p_name] = p_val

        has_json_body = False
        request_body = op.get("request_body") if isinstance(op.get("request_body"), dict) else {}
        content_types = request_body.get("content_types") if isinstance(request_body.get("content_types"), list) else []
        json_content_type = str(request_body.get("json_content_type") or "").strip()
        body_json = request_body.get("json_example")
        if body_json is not None:
            has_json_body = True
        for ct in content_types:
            if "json" in str(ct).lower():
                has_json_body = True
                if body_json is None:
                    body_json = {}
                break

        if json_content_type and not headers_obj.get("Content-Type"):
            headers_obj["Content-Type"] = json_content_type
        elif has_json_body and not headers_obj.get("Content-Type"):
            headers_obj["Content-Type"] = "application/json"
        responses = op.get("responses") if isinstance(op.get("responses"), list) else []
        if responses:
            first_resp = responses[0] if isinstance(responses[0], dict) else {}
            ct_list = first_resp.get("content_types") if isinstance(first_resp.get("content_types"), list) else []
            if ct_list and not headers_obj.get("Accept"):
                headers_obj["Accept"] = str(ct_list[0] or "").strip()

        case = {
            "name": name[:128] if name else f"OpenAPI用例{idx}",
            "description": op_desc or "由 OpenAPI 文档本地解析生成",
            "base_url": base_url,
            "path": path,
            "method": method,
            "headers": headers_obj or None,
            "params": params_obj or None,
            "body_json": body_json if body_json is not None else None,
            "body_text": None,
            "timeout_seconds": 10,
            "assert_status": 200,
            "assert_contains": "",
        }
        cases.append(case)
    return cases


@api_view(["POST"])
def ai_generate_from_openapi(request):
    schema_url = (request.data.get("schema_url") or "").strip() or None
    schema_text = request.data.get("schema_text")
    extra_requirements = (request.data.get("extra_requirements") or "").strip() or None
    ai_base_url = (request.data.get("ai_base_url") or "").strip() or None
    ai_api_key = (request.data.get("ai_api_key") or "").strip() or None
    ai_model = (request.data.get("ai_model") or "").strip() or None
    raw_timeout = request.data.get("ai_timeout_seconds")
    ai_timeout_seconds = None
    if raw_timeout not in (None, ""):
        try:
            ai_timeout_seconds = int(raw_timeout)
        except (TypeError, ValueError):
            return Response({"detail": "ai_timeout_seconds 必须是整数"}, status=status.HTTP_400_BAD_REQUEST)
        if ai_timeout_seconds <= 0 or ai_timeout_seconds > 300:
            return Response({"detail": "ai_timeout_seconds 取值范围为 1-300"}, status=status.HTTP_400_BAD_REQUEST)

    if not schema_url and not schema_text:
        return Response(
            {"detail": "schema_url 和 schema_text 至少提供一个"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        doc = load_openapi_document(schema_url=schema_url, schema_text=schema_text)
        summary = summarize_openapi_document(doc)
        api_key = str(ai_api_key or os.getenv("AI_API_KEY", "")).strip()
        if api_key:
            try:
                result = generate_test_cases_from_openapi_summary(
                    summary=summary,
                    extra_requirements=extra_requirements,
                    ai_base_url=ai_base_url,
                    ai_api_key=api_key,
                    ai_model=ai_model,
                    ai_timeout_seconds=ai_timeout_seconds,
                )
                cases = result["cases"]
                raw_content = result.get("raw_content")
                mode = "ai"
                message = ""
            except httpx.HTTPStatusError as exc:
                # AI 服务异常时自动回退本地解析，保证主流程可用。
                cases = _local_cases_from_openapi_summary(summary)
                raw_content = None
                mode = "local"
                message = f"AI 调用失败，已自动回退本地解析模式。{_httpx_error_detail('AI 接口调用失败', exc)}"
        else:
            # 未配置 Key 时直接走本地模式，避免前端空白。
            cases = _local_cases_from_openapi_summary(summary)
            raw_content = None
            mode = "local"
            message = "未配置 AI_API_KEY，已使用本地解析模式生成接口草稿"
        return Response(
            {
                "summary": summary,
                "cases": cases,
                "raw_content": raw_content,
                "mode": mode,
                "message": message,
            }
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except httpx.HTTPStatusError as exc:
        return Response(
            {"detail": _httpx_error_detail("外部接口调用失败", exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"OpenAPI 生成失败: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def ai_validate_config(request):
    ai_base_url = (request.data.get("ai_base_url") or "").strip() or None
    ai_api_key = (request.data.get("ai_api_key") or "").strip() or None
    ai_model = (request.data.get("ai_model") or "").strip() or None
    raw_timeout = request.data.get("ai_timeout_seconds")
    ai_timeout_seconds = None
    if raw_timeout not in (None, ""):
        try:
            ai_timeout_seconds = int(raw_timeout)
        except (TypeError, ValueError):
            return Response({"detail": "ai_timeout_seconds 必须是整数"}, status=status.HTTP_400_BAD_REQUEST)
        if ai_timeout_seconds <= 0 or ai_timeout_seconds > 300:
            return Response({"detail": "ai_timeout_seconds 取值范围为 1-300"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = validate_ai_connection(
            ai_base_url=ai_base_url,
            ai_api_key=ai_api_key,
            ai_model=ai_model,
            ai_timeout_seconds=ai_timeout_seconds,
        )
        return Response(result)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except httpx.HTTPStatusError as exc:
        return Response(
            {"detail": _httpx_error_detail("AI 接口调用失败", exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"AI 连通性检测失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
