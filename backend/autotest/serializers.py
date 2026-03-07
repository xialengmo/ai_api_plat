# 作者: lxl
# 说明: 业务模块实现。
from django.db import models
from rest_framework import serializers

from autotest.models import (
    ApiModule,
    MonitorPlatformTarget,
    MonitorPlatform,
    Project,
    ProjectEnvironment,
    RunHistory,
    ScenarioDataSet,
    ScenarioRunHistory,
    ScenarioStep,
    TestCase,
    TestScenario,
)


class ProjectSerializer(serializers.ModelSerializer):
    def validate_name(self, value: str) -> str:
        # 项目名全局唯一；更新时排除当前实例自身。
        name = (value or "").strip()
        qs = Project.objects.filter(name=name)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("项目名称已存在")
        return name

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]


class ProjectEnvironmentSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectEnvironment
        fields = [
            "id",
            "project",
            "project_id",
            "project_name",
            "name",
            "description",
            "base_url",
            "variables",
            "default_headers",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_base_url(self, value: str) -> str:
        # 仅接受显式协议，避免后续执行时 urljoin 出现歧义。
        raw = (value or "").strip()
        if not (raw.startswith("http://") or raw.startswith("https://")):
            raise serializers.ValidationError("base_url 必须以 http:// 或 https:// 开头")
        return raw

    def validate_default_headers(self, value):
        # 空值统一归一为 {}，便于前端渲染与执行器读取。
        if value in (None, "", {}):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("default_headers 必须是 JSON 对象")
        return value


class ApiModuleSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    parent_id = serializers.IntegerField(source="parent.id", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = ApiModule
        fields = [
            "id",
            "project",
            "project_id",
            "project_name",
            "parent",
            "parent_id",
            "parent_name",
            "name",
            "description",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value: str) -> str:
        return str(value or "").strip()

    def validate(self, attrs):
        # 模块父子关系校验：同项目、非自身、无环。
        instance = getattr(self, "instance", None)
        project = attrs.get("project") or (instance.project if instance else None)
        parent = attrs.get("parent") if "parent" in attrs else (instance.parent if instance else None)
        name = attrs.get("name") if "name" in attrs else (instance.name if instance else "")
        if parent and project and parent.project_id != project.id:
            raise serializers.ValidationError("父模块不属于当前项目")
        if instance and parent and parent.id == instance.id:
            raise serializers.ValidationError("父模块不能是自己")
        if instance and parent:
            cursor = parent
            while cursor:
                if cursor.id == instance.id:
                    raise serializers.ValidationError("父模块层级存在循环引用")
                cursor = cursor.parent

        if project and name:
            siblings = ApiModule.objects.filter(project_id=project.id, name=name)
            if parent:
                siblings = siblings.filter(parent_id=parent.id)
            else:
                siblings = siblings.filter(parent__isnull=True)
            if instance:
                siblings = siblings.exclude(id=instance.id)
            if siblings.exists():
                raise serializers.ValidationError("同一父模块下模块名称已存在")
        return attrs


class ScenarioDataSetSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    module_id = serializers.IntegerField(source="module.id", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    preview_rows = serializers.SerializerMethodField()
    row_count = serializers.SerializerMethodField()

    class Meta:
        model = ScenarioDataSet
        fields = [
            "id",
            "project",
            "project_id",
            "project_name",
            "module",
            "module_id",
            "module_name",
            "name",
            "description",
            "source_type",
            "data_rows",
            "raw_text",
            "enabled",
            "assert_enabled",
            "assert_targets",
            "assert_status_code",
            "assert_header_jsonpath",
            "assert_header_expected",
            "assert_response_jsonpath",
            "assert_response_expected",
            "preview_rows",
            "row_count",
            "created_at",
            "updated_at",
        ]

    def _parse_rows(self, obj) -> list:
        import csv
        import io
        import json

        rows = []
        source_type = str(obj.source_type or "table").strip().lower()
        # 三种输入形态统一转换为 list[dict]，供预览和执行复用。
        if source_type == "table":
            if isinstance(obj.data_rows, list):
                rows = [item for item in obj.data_rows if isinstance(item, dict)]
        elif source_type == "json":
            payload = obj.raw_text
            if isinstance(payload, str) and payload.strip():
                try:
                    parsed = json.loads(payload)
                except Exception:  # noqa: BLE001
                    parsed = None
                if isinstance(parsed, list):
                    rows = [item for item in parsed if isinstance(item, dict)]
                elif isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
                    rows = [item for item in parsed.get("rows") if isinstance(item, dict)]
        elif source_type == "csv":
            text = str(obj.raw_text or "").strip()
            if text:
                try:
                    reader = csv.DictReader(io.StringIO(text))
                    rows = [dict(item) for item in reader]
                except Exception:  # noqa: BLE001
                    rows = []
        normalized = []
        # 键名强制转字符串，避免 JSON 数字键导致前端表格列异常。
        for item in rows:
            normalized.append({str(k): v for k, v in item.items()})
        return normalized

    def get_preview_rows(self, obj):
        return self._parse_rows(obj)[:10]

    def get_row_count(self, obj):
        return len(self._parse_rows(obj))

    def _validate_project_module(self, attrs):
        # 数据集模块必须挂在同一项目，避免跨项目串数据。
        instance = getattr(self, "instance", None)
        project = attrs.get("project") or (instance.project if instance else None)
        module = attrs.get("module") if "module" in attrs else (instance.module if instance else None)
        if module and project and module.project_id != project.id:
            raise serializers.ValidationError("数据集所属模块不属于当前项目")
        return attrs

    def validate_source_type(self, value: str) -> str:
        source_type = str(value or "table").strip().lower()
        if source_type not in {"table", "json", "csv"}:
            raise serializers.ValidationError("source_type 仅支持 table/json/csv")
        return source_type

    def validate_data_rows(self, value):
        if value in (None, "", []):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("data_rows 必须是数组")
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("data_rows 每一行必须是对象")
        return value

    def validate_assert_targets(self, value):
        # 断言目标白名单 + 去重，防止重复断言造成结果噪音。
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("assert_targets 必须是数组")
        allowed = {"status_code", "request_headers", "response_body"}
        normalized = []
        for item in value:
            key = str(item or "").strip().lower()
            if key not in allowed:
                raise serializers.ValidationError("assert_targets 仅支持 status_code/request_headers/response_body")
            if key not in normalized:
                normalized.append(key)
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs = self._validate_project_module(attrs)
        instance = getattr(self, "instance", None)
        assert_enabled = attrs.get("assert_enabled")
        if assert_enabled is None and instance is not None:
            assert_enabled = bool(instance.assert_enabled)
        if not assert_enabled:
            return attrs

        targets = attrs.get("assert_targets")
        if targets is None and instance is not None:
            targets = instance.assert_targets or []
        targets = targets or []
        # 启用断言后至少选择一类目标，否则视为无效配置。
        if not targets:
            raise serializers.ValidationError("启用断言后请至少选择一种断言方式")

        if "status_code" in targets:
            status_code = attrs.get("assert_status_code")
            if status_code is None and instance is not None:
                status_code = instance.assert_status_code
            if status_code is None:
                raise serializers.ValidationError("请配置状态码断言值")

        if "request_headers" in targets:
            jsonpath = attrs.get("assert_header_jsonpath")
            expected = attrs.get("assert_header_expected")
            if jsonpath is None and instance is not None:
                jsonpath = instance.assert_header_jsonpath
            if expected is None and instance is not None:
                expected = instance.assert_header_expected
            if not str(jsonpath or "").strip():
                raise serializers.ValidationError("请配置请求头 JSONPath")
            if not str(expected or "").strip():
                raise serializers.ValidationError("请配置请求头期望值")

        if "response_body" in targets:
            jsonpath = attrs.get("assert_response_jsonpath")
            expected = attrs.get("assert_response_expected")
            if jsonpath is None and instance is not None:
                jsonpath = instance.assert_response_jsonpath
            if expected is None and instance is not None:
                expected = instance.assert_response_expected
            if not str(jsonpath or "").strip():
                raise serializers.ValidationError("请配置响应结果 JSONPath")
            if not str(expected or "").strip():
                raise serializers.ValidationError("请配置响应结果期望值")

        return attrs


class TestCaseSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_id = serializers.IntegerField(source="environment.id", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    module_id = serializers.IntegerField(source="module.id", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "name",
            "description",
            "base_url",
            "path",
            "method",
            "headers",
            "params",
            "body_json",
            "body_text",
            "timeout_seconds",
            "verify_ssl",
            "assert_status",
            "assert_contains",
            "custom_assertions",
            "environment",
            "environment_id",
            "environment_name",
            "module",
            "module_id",
            "module_name",
            "project",
            "project_id",
            "project_name",
            "created_at",
            "updated_at",
        ]

    def validate_method(self, value: str) -> str:
        return value.upper()

    def validate_base_url(self, value: str) -> str:
        raw = (value or "").strip()
        if not (raw.startswith("http://") or raw.startswith("https://")):
            raise serializers.ValidationError("base_url 必须以 http:// 或 https:// 开头")
        return raw

    def validate(self, attrs):
        # 用例关联资源（环境/模块）必须与项目一致，避免执行越权。
        instance = getattr(self, "instance", None)
        project = attrs.get("project") or (instance.project if instance else None)

        if "environment" in attrs:
            environment = attrs.get("environment")
        else:
            environment = instance.environment if instance else None

        if environment and project and environment.project_id != project.id:
            raise serializers.ValidationError("所选环境不属于当前项目")
        module = attrs.get("module") if "module" in attrs else (instance.module if instance else None)
        if module and project and module.project_id != project.id:
            raise serializers.ValidationError("所选模块不属于当前项目")
        return attrs


class RunHistorySerializer(serializers.ModelSerializer):
    test_case_id = serializers.IntegerField(source="test_case.id", read_only=True)

    class Meta:
        model = RunHistory
        fields = [
            "id",
            "test_case_id",
            "success",
            "status_code",
            "response_time_ms",
            "error_message",
            "request_snapshot",
            "response_headers",
            "response_content_type",
            "response_body",
            "assertion_result",
            "created_at",
        ]


class ScenarioStepSerializer(serializers.ModelSerializer):
    test_case_name = serializers.CharField(source="test_case.name", read_only=True)

    class Meta:
        model = ScenarioStep
        fields = [
            "id",
            "scenario",
            "step_order",
            "step_name",
            "test_case",
            "test_case_name",
            "enabled",
            "continue_on_fail",
            "overrides",
            "extract_rules",
            "preconditions",
            "assertions",
            "pre_processors",
            "post_processors",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "scenario": {"required": False},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
        }


class TestScenarioSerializer(serializers.ModelSerializer):
    steps = ScenarioStepSerializer(many=True)
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    module_id = serializers.IntegerField(source="module.id", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    data_set_id = serializers.IntegerField(source="data_set.id", read_only=True)
    data_set_name = serializers.CharField(source="data_set.name", read_only=True)

    class Meta:
        model = TestScenario
        fields = [
            "id",
            "name",
            "description",
            "project",
            "project_id",
            "project_name",
            "module",
            "module_id",
            "module_name",
            "param_enabled",
            "data_set",
            "data_set_id",
            "data_set_name",
            "data_mode",
            "data_pick",
            "param_retry_count",
            "sort_order",
            "stop_on_failure",
            "steps",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "project": {"read_only": True},
        }

    def validate_name(self, value: str) -> str:
        return str(value or "").strip()

    def validate(self, attrs):
        # 场景维度校验：步骤项目一致、参数化依赖完整、运行参数合法。
        instance = getattr(self, "instance", None)
        module = attrs.get("module") if "module" in attrs else (instance.module if instance else None)
        if not module:
            raise serializers.ValidationError("场景必须关联模块")
        project = module.project
        attrs["project"] = project
        data_set = attrs.get("data_set") if "data_set" in attrs else (instance.data_set if instance else None)
        param_enabled = attrs.get("param_enabled") if "param_enabled" in attrs else (
            instance.param_enabled if instance else False
        )
        name = attrs.get("name") if "name" in attrs else (instance.name if instance else "")
        steps_data = attrs.get("steps")
        if module and steps_data is not None:
            for step in steps_data:
                test_case = step.get("test_case")
                if test_case and test_case.project_id != module.project_id:
                    raise serializers.ValidationError("场景步骤中的接口不属于所选模块项目")
        if data_set and module and data_set.project_id != module.project_id:
            raise serializers.ValidationError("场景数据集与场景模块不在同一项目")
        if param_enabled and not data_set:
            raise serializers.ValidationError("启用参数化时必须选择数据集")
        mode = str(attrs.get("data_mode") if "data_mode" in attrs else (instance.data_mode if instance else "all"))
        if mode not in {"all", "range", "random"}:
            raise serializers.ValidationError("data_mode 仅支持 all/range/random")
        retry_count = attrs.get("param_retry_count") if "param_retry_count" in attrs else (
            instance.param_retry_count if instance else 0
        )
        try:
            retry_count = int(retry_count or 0)
        except (TypeError, ValueError):
            raise serializers.ValidationError("param_retry_count 必须是整数")
        if retry_count < 0 or retry_count > 10:
            raise serializers.ValidationError("param_retry_count 取值范围 0-10")
        if project and name:
            queryset = TestScenario.objects.filter(project_id=project.id, name=name)
            if instance:
                queryset = queryset.exclude(id=instance.id)
            if queryset.exists():
                raise serializers.ValidationError("当前项目下场景名称已存在")
        return attrs

    def create(self, validated_data):
        # 未显式传 sort_order 时自动追加到当前模块末尾。
        steps_data = validated_data.pop("steps", [])
        if "sort_order" not in validated_data or validated_data.get("sort_order") is None:
            module = validated_data.get("module")
            if module:
                max_order = (
                    TestScenario.objects.filter(module=module).aggregate(models.Max("sort_order")).get("sort_order__max")
                    or 0
                )
            else:
                max_order = (
                    TestScenario.objects.filter(module__isnull=True).aggregate(models.Max("sort_order")).get("sort_order__max")
                    or 0
                )
            validated_data["sort_order"] = int(max_order) + 1
        scenario = TestScenario.objects.create(**validated_data)
        for step in steps_data:
            ScenarioStep.objects.create(scenario=scenario, **step)
        return scenario

    def update(self, instance, validated_data):
        # 步骤采用整包替换，确保前端拖拽排序后顺序可预测。
        steps_data = validated_data.pop("steps", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()

        if steps_data is not None:
            instance.steps.all().delete()
            for step in steps_data:
                ScenarioStep.objects.create(scenario=instance, **step)
        return instance


class ScenarioRunHistorySerializer(serializers.ModelSerializer):
    scenario_id = serializers.IntegerField(source="scenario.id", read_only=True)
    scenario_name = serializers.SerializerMethodField()

    def get_scenario_name(self, obj):
        # 批量执行报告优先显示快照中的报告名，其次回退到场景名。
        snapshot = obj.context_snapshot if isinstance(obj.context_snapshot, dict) else {}
        report_name = snapshot.get("__report_name")
        if report_name:
            return report_name
        if obj.scenario_id:
            return obj.scenario.name
        return f"Scenario #{obj.scenario_id}"

    class Meta:
        model = ScenarioRunHistory
        fields = [
            "id",
            "scenario_id",
            "scenario_name",
            "success",
            "duration_ms",
            "results",
            "iterations",
            "context_snapshot",
            "error_message",
            "created_at",
        ]


class MonitorPlatformSerializer(serializers.ModelSerializer):
    ssh_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    has_password = serializers.SerializerMethodField()
    monitor_targets = serializers.ListSerializer(child=serializers.DictField(), required=False)

    class Meta:
        model = MonitorPlatform
        fields = [
            "id",
            "name",
            "platform_type",
            "host",
            "ssh_port",
            "ssh_username",
            "ssh_password",
            "monitor_targets",
            "deploy_mode",
            "offline_package_name",
            "status",
            "prometheus_url",
            "grafana_url",
            "alertmanager_url",
            "last_error",
            "last_deployed_at",
            "deploy_logs",
            "created_by",
            "created_by_username",
            "has_password",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "offline_package_name",
            "status",
            "prometheus_url",
            "grafana_url",
            "alertmanager_url",
            "last_error",
            "last_deployed_at",
            "deploy_logs",
            "created_by",
            "created_by_username",
            "has_password",
            "created_at",
            "updated_at",
        ]

    def get_has_password(self, obj):
        return bool(str(obj.ssh_password or "").strip())

    def validate_ssh_port(self, value):
        port = int(value or 22)
        if port <= 0 or port > 65535:
            raise serializers.ValidationError("ssh_port 取值范围为 1-65535")
        return port

    def validate_deploy_mode(self, value: str) -> str:
        mode = str(value or "").strip().lower()
        if mode not in {MonitorPlatform.DEPLOY_MODE_ONLINE, MonitorPlatform.DEPLOY_MODE_OFFLINE}:
            raise serializers.ValidationError("deploy_mode 仅支持 online/offline")
        return mode

    def validate_platform_type(self, value: str) -> str:
        platform_type = str(value or "").strip().lower()
        if platform_type not in {MonitorPlatform.PLATFORM_TYPE_SINGLE, MonitorPlatform.PLATFORM_TYPE_HOST_CLUSTER}:
            raise serializers.ValidationError("platform_type 仅支持 single/host_cluster")
        return platform_type

    def validate_monitor_targets(self, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise serializers.ValidationError("monitor_targets 必须是数组")
        normalized = []
        host_seen = set()
        for idx, row in enumerate(value):
            if not isinstance(row, dict):
                continue
            host = str(row.get("host") or "").strip()
            if not host or host in host_seen:
                continue
            host_seen.add(host)
            name = str(row.get("name") or "").strip() or None
            try:
                node_port = int(row.get("node_exporter_port") or 9100)
            except Exception:
                raise serializers.ValidationError(f"monitor_targets[{idx}].node_exporter_port 必须是整数")
            try:
                cadvisor_port = int(row.get("cadvisor_port") or 8080)
            except Exception:
                raise serializers.ValidationError(f"monitor_targets[{idx}].cadvisor_port 必须是整数")
            if node_port <= 0 or node_port > 65535:
                raise serializers.ValidationError(f"monitor_targets[{idx}].node_exporter_port 取值范围为 1-65535")
            if cadvisor_port <= 0 or cadvisor_port > 65535:
                raise serializers.ValidationError(f"monitor_targets[{idx}].cadvisor_port 取值范围为 1-65535")
            enabled = bool(row.get("enabled", True))
            normalized.append(
                {
                    "name": name,
                    "host": host,
                    "node_exporter_port": node_port,
                    "cadvisor_port": cadvisor_port,
                    "enabled": enabled,
                    "sort_order": idx,
                }
            )
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        platform_type = str(attrs.get("platform_type") or (instance.platform_type if instance else MonitorPlatform.PLATFORM_TYPE_SINGLE)).strip().lower()
        monitor_targets = attrs.get("monitor_targets", None)
        if platform_type == MonitorPlatform.PLATFORM_TYPE_HOST_CLUSTER:
            if monitor_targets is None:
                existing_enabled = (
                    instance.monitor_targets.filter(enabled=True).exists() if instance is not None else False
                )
                if not existing_enabled:
                    raise serializers.ValidationError("host_cluster 模式至少需要一个启用的监控目标")
            else:
                enabled_count = sum(1 for item in monitor_targets if bool(item.get("enabled")))
                if enabled_count <= 0:
                    raise serializers.ValidationError("host_cluster 模式至少需要一个启用的监控目标")
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        rows = instance.monitor_targets.all().order_by("sort_order", "id")
        data["monitor_targets"] = [
            {
                "id": int(item.id),
                "name": item.name,
                "host": item.host,
                "node_exporter_port": int(item.node_exporter_port or 9100),
                "cadvisor_port": int(item.cadvisor_port or 8080),
                "enabled": bool(item.enabled),
                "sort_order": int(item.sort_order or 0),
            }
            for item in rows
        ]
        return data

    def _replace_monitor_targets(self, instance, rows):
        use_rows = list(rows or [])
        MonitorPlatformTarget.objects.filter(platform_id=instance.id).delete()
        objects = []
        for idx, row in enumerate(use_rows):
            host = str(row.get("host") or "").strip()
            if not host:
                continue
            objects.append(
                MonitorPlatformTarget(
                    platform=instance,
                    name=row.get("name"),
                    host=host,
                    node_exporter_port=int(row.get("node_exporter_port") or 9100),
                    cadvisor_port=int(row.get("cadvisor_port") or 8080),
                    enabled=bool(row.get("enabled", True)),
                    sort_order=int(row.get("sort_order") if row.get("sort_order") is not None else idx),
                )
            )
        if objects:
            MonitorPlatformTarget.objects.bulk_create(objects)

    def update(self, instance, validated_data):
        # 更新时若未传 ssh_password，则保留原密码，避免意外清空导致后续部署失败。
        if "ssh_password" not in validated_data:
            validated_data["ssh_password"] = instance.ssh_password
        monitor_targets = validated_data.pop("monitor_targets", None)
        updated = super().update(instance, validated_data)
        if monitor_targets is not None:
            self._replace_monitor_targets(updated, monitor_targets)
        return updated

    def create(self, validated_data):
        monitor_targets = validated_data.pop("monitor_targets", None)
        instance = super().create(validated_data)
        self._replace_monitor_targets(instance, monitor_targets)
        return instance


