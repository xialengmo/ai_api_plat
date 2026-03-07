# 作者: lxl
# 说明: 测试用例/场景执行引擎与变量解析。
import copy
import csv
import hashlib
import hmac
import base64
import io
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urljoin, quote, unquote

import httpx
try:
    from jsonpath_ng.ext import parse as jsonpath_parse
except Exception:  # noqa: BLE001
    jsonpath_parse = None

from autotest.models import GlobalVariable, ProjectEnvironment, ScenarioStep, TestCase, TestScenario


VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_\-\u4e00-\u9fa5]+)\s*\}\}")
ROW_VAR_PATTERN = re.compile(r"\{\{\s*row\.([A-Za-z0-9_\-\u4e00-\u9fa5]+)\s*\}\}")
ENV_REF_PATTERN = re.compile(
    r"&([A-Za-z0-9_\u4e00-\u9fa5]+(?:\|[A-Za-z_][A-Za-z0-9_]*(?::[^&\s]*)?)*)"
)
CONCAT_ENV_PATTERN = re.compile(
    r"(&[A-Za-z0-9_\u4e00-\u9fa5]+(?:\+&[A-Za-z0-9_\u4e00-\u9fa5]+)+"
    r"(?:\|[A-Za-z_][A-Za-z0-9_]*(?::[^&\s]*)?)*)"
)

BUILTIN_KEY = "__builtin__"
_JSONPATH_CACHE = {}


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _to_number(value):
    if isinstance(value, (int, float)):
        return value
    text = _to_text(value).strip()
    if text == "":
        return 0
    if "." in text:
        return float(text)
    return int(text)


def _decode_base64_text(raw: str) -> str:
    text = _to_text(raw).strip()
    if text == "":
        return ""
    padded = text + "=" * ((4 - len(text) % 4) % 4)
    try:
        return base64.b64decode(padded).decode("utf-8")
    except Exception:
        return base64.urlsafe_b64decode(padded).decode("utf-8")


def _resolve_builtin_value(name: str):
    key = str(name or "").strip().lower()
    if key in {"timestamp", "timestamp_int"}:
        return int(time.time())
    if key in {"timestamp_ms", "timestamp_millis"}:
        return int(time.time() * 1000)
    if key in {"date_ymd", "today_ymd"}:
        return datetime.now().strftime("%Y-%m-%d")
    if key in {"datetime", "now"}:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if key in {"phone", "phone_cn", "mobile"}:
        second = str(random.randint(3, 9))
        rest = "".join(str(random.randint(0, 9)) for _ in range(9))
        return f"1{second}{rest}"
    return None


def _safe_parse_json(raw_text):
    if raw_text is None:
        return None
    text = str(raw_text).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _resolve_environment_variables(raw_vars):
    if not isinstance(raw_vars, dict):
        return {}
    resolved = {}
    for key, value in raw_vars.items():
        if isinstance(value, dict) and BUILTIN_KEY in value:
            builtin_value = _resolve_builtin_value(value.get(BUILTIN_KEY))
            resolved[key] = builtin_value if builtin_value is not None else ""
            continue
        resolved[key] = value
    return resolved


def _normalize_data_row(row) -> dict:
    if not isinstance(row, dict):
        return {}
    return {str(k): v for k, v in row.items()}


def _parse_data_set_rows(data_set) -> list:
    if data_set is None:
        return []
    source_type = str(getattr(data_set, "source_type", "table") or "table").strip().lower()
    rows = []
    if source_type == "table":
        payload = getattr(data_set, "data_rows", None)
        if isinstance(payload, list):
            rows = [_normalize_data_row(item) for item in payload if isinstance(item, dict)]
    elif source_type == "json":
        raw_text = str(getattr(data_set, "raw_text", "") or "").strip()
        if raw_text:
            try:
                parsed = json.loads(raw_text)
            except Exception:  # noqa: BLE001
                parsed = None
            if isinstance(parsed, list):
                rows = [_normalize_data_row(item) for item in parsed if isinstance(item, dict)]
            elif isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
                rows = [_normalize_data_row(item) for item in parsed.get("rows") if isinstance(item, dict)]
    elif source_type == "csv":
        raw_text = str(getattr(data_set, "raw_text", "") or "").strip()
        if raw_text:
            try:
                reader = csv.DictReader(io.StringIO(raw_text))
                rows = [_normalize_data_row(dict(item)) for item in reader]
            except Exception:  # noqa: BLE001
                rows = []
    return rows


def _pick_data_rows(rows: list, mode: str, pick: Optional[str], runtime_options: Optional[dict] = None) -> list:
    # 运行参数优先于场景默认值，支持 all / range / random 三种取数策略。
    if not rows:
        return []
    options = runtime_options or {}
    run_mode = str(options.get("data_mode") or mode or "all").strip().lower()
    run_pick = str(options.get("data_pick") if options.get("data_pick") is not None else (pick or "")).strip()
    if run_mode == "all":
        return rows
    if run_mode == "range":
        if not run_pick:
            return rows
        selected_indexes = set()
        for part in [item.strip() for item in run_pick.split(",") if item.strip()]:
            if "-" in part:
                left, _, right = part.partition("-")
                try:
                    start = int(left)
                    end = int(right)
                except Exception:  # noqa: BLE001
                    continue
                if start > end:
                    start, end = end, start
                for idx in range(start, end + 1):
                    selected_indexes.add(idx - 1)
            else:
                try:
                    selected_indexes.add(int(part) - 1)
                except Exception:  # noqa: BLE001
                    continue
        return [row for idx, row in enumerate(rows) if idx in selected_indexes]
    if run_mode == "random":
        try:
            count = int(run_pick or 1)
        except Exception:  # noqa: BLE001
            count = 1
        count = max(1, min(count, len(rows)))
        return random.sample(rows, count)
    return rows


def _apply_transform(value, op: str, arg: Optional[str], context: dict):
    op = (op or "").strip().lower()
    arg = _render_value(arg, context) if arg else None

    if op in {"str", "string"}:
        return _to_text(value)
    if op == "int":
        return int(_to_number(value))
    if op == "float":
        return float(_to_number(value))
    if op == "lower":
        return _to_text(value).lower()
    if op == "upper":
        return _to_text(value).upper()
    if op == "strip":
        return _to_text(value).strip()
    if op == "md5":
        return hashlib.md5(_to_text(value).encode("utf-8")).hexdigest()
    if op == "sha1":
        return hashlib.sha1(_to_text(value).encode("utf-8")).hexdigest()
    if op == "sha256":
        return hashlib.sha256(_to_text(value).encode("utf-8")).hexdigest()
    if op == "hmac_sha256":
        secret = _to_text(arg)
        return hmac.new(secret.encode("utf-8"), _to_text(value).encode("utf-8"), hashlib.sha256).hexdigest()
    if op in {"base64", "base64_encode"}:
        return base64.b64encode(_to_text(value).encode("utf-8")).decode("utf-8")
    if op == "base64_decode":
        return _decode_base64_text(_to_text(value))
    if op == "url_encode":
        return quote(_to_text(value), safe="")
    if op == "url_decode":
        return unquote(_to_text(value))
    if op == "json_dumps":
        return json.dumps(value, ensure_ascii=False)
    if op == "json_loads":
        return json.loads(_to_text(value))
    if op == "timestamp":
        return int(time.time())
    if op == "timestamp_ms":
        return int(time.time() * 1000)
    if op == "datetime":
        fmt = _to_text(arg) if arg else "%Y-%m-%d %H:%M:%S"
        return datetime.now().strftime(fmt)
    if op in {"add_seconds", "add_minutes", "add_hours", "add_days"}:
        delta_num = int(_to_number(arg or 0))
        base_num = int(_to_number(value))
        if op == "add_seconds":
            return base_num + delta_num
        if op == "add_minutes":
            return base_num + delta_num * 60
        if op == "add_hours":
            return base_num + delta_num * 3600
        return base_num + delta_num * 86400
    if op == "format_datetime":
        fmt = _to_text(arg) if arg else "%Y-%m-%d %H:%M:%S"
        base_ts = int(_to_number(value))
        return datetime.fromtimestamp(base_ts).strftime(fmt)
    raise ValueError(f"unsupported transform: {op}")


def _resolve_env_expression(expr: str, context: dict):
    # 解析单变量表达式：&token|base64|url_encode
    parts = [part for part in str(expr or "").split("|") if part != ""]
    if not parts:
        return ""
    key = parts[0]
    value = context.get(key)
    if value is None:
        return f"&{expr}"
    for step in parts[1:]:
        op, _, raw_arg = step.partition(":")
        arg = raw_arg if raw_arg != "" else None
        value = _apply_transform(value, op, arg, context)
    return value


def _resolve_concat_env_expression(expr: str, context: dict):
    # 解析拼接表达式：&appid+&timestamp|md5
    text = str(expr or "")
    head, sep, tail = text.partition("|")
    terms = [item.strip() for item in head.split("+") if item.strip()]
    if not terms:
        return f"&{expr}"
    pieces = []
    for term in terms:
        if not term.startswith("&"):
            pieces.append(term)
            continue
        key = term[1:]
        value = context.get(key, term)
        pieces.append(_to_text(value))
    merged = "".join(pieces)
    if not sep:
        return merged
    transform_steps = [step for step in tail.split("|") if step]
    current = merged
    for step in transform_steps:
        op, _, raw_arg = step.partition(":")
        arg = raw_arg if raw_arg != "" else None
        current = _apply_transform(current, op, arg, context)
    return current


def _render_value(value, context: dict):
    if isinstance(value, str):
        # 顺序很关键：先替换 row 变量，再替换普通变量，最后处理环境表达式。
        def row_repl(match):
            key = match.group(1)
            row = context.get("row")
            if isinstance(row, dict) and key in row:
                return str(row.get(key))
            return match.group(0)

        rendered = ROW_VAR_PATTERN.sub(row_repl, value)

        def repl(match):
            key = match.group(1)
            return str(context.get(key, match.group(0)))

        rendered = VAR_PATTERN.sub(repl, rendered)

        def concat_env_repl(match):
            expr = match.group(1)
            try:
                resolved = _resolve_concat_env_expression(expr, context)
            except Exception:
                return match.group(0)
            return _to_text(resolved)

        rendered = CONCAT_ENV_PATTERN.sub(concat_env_repl, rendered)

        def env_repl(match):
            expr = match.group(1)
            try:
                resolved = _resolve_env_expression(expr, context)
            except Exception:
                return match.group(0)
            return _to_text(resolved)

        return ENV_REF_PATTERN.sub(env_repl, rendered)
    if isinstance(value, dict):
        return {k: _render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(v, context) for v in value]
    return value


def _case_to_dict(test_case: TestCase) -> dict:
    env = getattr(test_case, "environment", None)
    environment_base_url = env.base_url if env else None
    environment_variables = copy.deepcopy(env.variables) if env else None
    return {
        "name": test_case.name,
        "project_id": test_case.project_id,
        "environment_id": test_case.environment_id,
        "base_url": test_case.base_url,
        "environment_base_url": environment_base_url,
        "environment_variables": environment_variables or {},
        "path": test_case.path,
        "method": test_case.method,
        "headers": copy.deepcopy(test_case.headers) or {},
        "params": copy.deepcopy(test_case.params) or None,
        "body_json": copy.deepcopy(test_case.body_json),
        "body_text": test_case.body_text,
        "timeout_seconds": test_case.timeout_seconds,
        "verify_ssl": test_case.verify_ssl,
        "assert_status": test_case.assert_status,
        "assert_contains": test_case.assert_contains,
        "custom_assertions": copy.deepcopy(test_case.custom_assertions) or None,
    }


def _resolve_runtime_environment_override(scenario: TestScenario, runtime_options: Optional[dict]) -> Optional[dict]:
    # 场景执行时允许临时切换环境，但必须限定在当前项目内。
    raw_env_id = (runtime_options or {}).get("environment_id")
    try:
        environment_id = int(raw_env_id)
    except (TypeError, ValueError):
        return None
    if environment_id <= 0:
        return None

    project_id = None
    module = getattr(scenario, "module", None)
    if module is not None:
        project_id = getattr(module, "project_id", None)

    queryset = ProjectEnvironment.objects.filter(id=environment_id)
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    env = queryset.first()
    if not env:
        return None
    return {
        "environment_id": env.id,
        "environment_base_url": env.base_url if env.base_url else None,
        "environment_variables": copy.deepcopy(env.variables) if isinstance(env.variables, dict) else {},
    }


def _load_global_variables(project_id) -> dict:
    if not project_id:
        return {}
    rows = GlobalVariable.objects.filter(project_id=project_id).values("name", "value")
    result = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        result[name] = row.get("value")
    return result


def _persist_runtime_variable(*, var_type: str, target: str, value, project_id=None, environment_id=None):
    # 将后置处理器提取出的变量落库，支持全局变量和环境变量两种持久化域。
    if not target:
        return
    if var_type == "global" and project_id:
        GlobalVariable.objects.update_or_create(
            project_id=project_id,
            name=target,
            defaults={"value": value},
        )
    elif var_type == "environment" and environment_id:
        env = ProjectEnvironment.objects.filter(id=environment_id).first()
        if not env:
            return
        variables = copy.deepcopy(env.variables) if isinstance(env.variables, dict) else {}
        variables[target] = value
        env.variables = variables
        env.save(update_fields=["variables", "updated_at"])


def _merge_case_config(base: dict, overrides: Optional[dict]) -> dict:
    if not overrides:
        return base
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        merged[key] = value
    return merged


def _step_value(step, key: str, default=None):
    if isinstance(step, dict):
        return step.get(key, default)
    return getattr(step, key, default)


def _step_test_case(step):
    return _step_value(step, "test_case")


def _prepare_runtime_case(case_config: dict, context: Optional[dict] = None) -> tuple:
    global_vars = _load_global_variables(case_config.get("project_id"))
    resolved_globals = _resolve_environment_variables(copy.deepcopy(global_vars))
    resolved_env = _resolve_environment_variables(copy.deepcopy(case_config.get("environment_variables") or {}))
    context_vars = {}
    context_vars.update(resolved_globals)
    context_vars.update(resolved_env)
    if isinstance(context, dict):
        context_vars.update(copy.deepcopy(context))

    base_url = case_config.get("environment_base_url") or case_config["base_url"]
    rendered_base_url = _render_value(base_url, context_vars)
    rendered_path = _render_value(case_config["path"], context_vars)
    rendered_headers = _render_value(copy.deepcopy(case_config.get("headers") or {}), context_vars)
    rendered_params = _render_value(copy.deepcopy(case_config.get("params") or None), context_vars)
    rendered_body_json = _render_value(copy.deepcopy(case_config.get("body_json")), context_vars)
    rendered_body_text = _render_value(case_config.get("body_text"), context_vars)
    url = urljoin(str(rendered_base_url).rstrip("/") + "/", str(rendered_path).lstrip("/"))
    request_info = {
        "url": url,
        "method": str(case_config.get("method") or "GET").upper(),
        "headers": rendered_headers,
        "params": rendered_params,
        "body_json": rendered_body_json,
        "body_text": rendered_body_text,
        "base_url": rendered_base_url,
        "path": rendered_path,
        "timeout_seconds": int(case_config.get("timeout_seconds") or 10),
        "verify_ssl": bool(case_config.get("verify_ssl", True)),
    }
    rendered_config = copy.deepcopy(case_config)
    rendered_config["base_url"] = rendered_base_url
    rendered_config["path"] = rendered_path
    rendered_config["headers"] = rendered_headers
    rendered_config["params"] = rendered_params
    rendered_config["body_json"] = rendered_body_json
    rendered_config["body_text"] = rendered_body_text
    rendered_config["method"] = request_info["method"]
    return request_info, rendered_config, context_vars


def _collect_unresolved_placeholders(value, bucket=None):
    if bucket is None:
        bucket = set()
    if isinstance(value, str):
        for key in ROW_VAR_PATTERN.findall(value):
            bucket.add(f"{{{{row.{key}}}}}")
        for key in VAR_PATTERN.findall(value):
            bucket.add(f"{{{{{key}}}}}")
        return bucket
    if isinstance(value, dict):
        for item in value.values():
            _collect_unresolved_placeholders(item, bucket)
        return bucket
    if isinstance(value, list):
        for item in value:
            _collect_unresolved_placeholders(item, bucket)
        return bucket
    return bucket


def preview_runtime_case(case_config: dict, context: Optional[dict] = None) -> dict:
    request_info, rendered_config, render_context = _prepare_runtime_case(case_config, context=context)
    unresolved = sorted(_collect_unresolved_placeholders(request_info))
    return {
        "request": request_info,
        "assertions": _build_step_assertion_summary(rendered_config, []),
        "unresolved_placeholders": unresolved,
        "context_keys": sorted(
            [str(key) for key in render_context.keys() if str(key or "") and not str(key).startswith("__")]
        ),
    }


def _build_scenario_preview_context(scenario: TestScenario, runtime_options: Optional[dict] = None, initial_context: Optional[dict] = None):
    context = dict(initial_context or {})
    preview_row = {}
    runtime_env_override = _resolve_runtime_environment_override(scenario, runtime_options)

    runtime_param_enabled = (runtime_options or {}).get("param_enabled")
    scenario_param_enabled = bool(getattr(scenario, "param_enabled", False))
    param_enabled = scenario_param_enabled if runtime_param_enabled is not False else False
    if param_enabled and getattr(scenario, "data_set_id", None):
        rows = _parse_data_set_rows(getattr(scenario, "data_set", None))
        rows = _pick_data_rows(
            rows,
            str(getattr(scenario, "data_mode", "all") or "all"),
            getattr(scenario, "data_pick", None),
            runtime_options=runtime_options,
        )
        if rows:
            preview_row = copy.deepcopy(rows[0] or {})
            context["row"] = copy.deepcopy(preview_row)
            context.update(copy.deepcopy(preview_row))
    return context, preview_row, runtime_env_override


def preview_scenario_steps(
    scenario: TestScenario,
    steps: list,
    runtime_options: Optional[dict] = None,
    initial_context: Optional[dict] = None,
) -> dict:
    context, preview_row, runtime_env_override = _build_scenario_preview_context(
        scenario,
        runtime_options=runtime_options,
        initial_context=initial_context,
    )
    previews = []
    for index, step in enumerate(steps or []):
        test_case = _step_test_case(step)
        if test_case is None:
            continue
        preview_context = copy.deepcopy(context)
        base_config = _case_to_dict(test_case)
        if runtime_env_override:
            base_config["environment_id"] = runtime_env_override.get("environment_id")
            base_config["environment_base_url"] = runtime_env_override.get("environment_base_url")
            base_config["environment_variables"] = copy.deepcopy(runtime_env_override.get("environment_variables") or {})
        merged_config = _merge_case_config(base_config, _step_value(step, "overrides") or {})
        pre_processor_logs = _run_processors(
            _step_value(step, "pre_processors"),
            phase="pre",
            context=preview_context,
            response=None,
            response_json=None,
            project_id=base_config.get("project_id"),
            environment_id=base_config.get("environment_id"),
        )
        case_preview = preview_runtime_case(merged_config, context=preview_context)
        previews.append(
            {
                "step_index": index,
                "step_id": _step_value(step, "id"),
                "step_order": _step_value(step, "step_order", index + 1),
                "step_name": _step_value(step, "step_name") or f"步骤{index + 1}",
                "test_case_id": getattr(test_case, "id", None),
                "test_case_name": getattr(test_case, "name", ""),
                "enabled": bool(_step_value(step, "enabled", True)),
                "continue_on_fail": bool(_step_value(step, "continue_on_fail", False)),
                "request": case_preview.get("request") or {},
                "assertions": _build_step_assertion_summary(
                    {
                        **merged_config,
                        "assert_status": merged_config.get("assert_status"),
                        "assert_contains": merged_config.get("assert_contains"),
                        "custom_assertions": merged_config.get("custom_assertions"),
                    },
                    copy.deepcopy(_step_value(step, "assertions") or []),
                ),
                "preconditions": copy.deepcopy(_step_value(step, "preconditions") or []),
                "extract_rules": copy.deepcopy(_step_value(step, "extract_rules") or []),
                "pre_processors": pre_processor_logs,
                "post_processors": copy.deepcopy(_step_value(step, "post_processors") or []),
                "unresolved_placeholders": case_preview.get("unresolved_placeholders") or [],
            }
        )
        context.update({key: value for key, value in preview_context.items() if str(key) != "row"})
        if "row" in preview_context:
            context["row"] = copy.deepcopy(preview_context.get("row") or {})
    return {
        "summary": {
            "step_count": len(steps or []),
            "enabled_step_count": sum(1 for item in (steps or []) if bool(_step_value(item, "enabled", True))),
            "param_enabled": bool(getattr(scenario, "param_enabled", False)),
            "preview_row": preview_row,
        },
        "steps": previews,
    }


def debug_scenario_step(
    scenario: TestScenario,
    steps: list,
    step_index: int,
    runtime_options: Optional[dict] = None,
    initial_context: Optional[dict] = None,
    include_previous: bool = True,
) -> dict:
    if step_index < 0 or step_index >= len(steps or []):
        raise IndexError("step_index out of range")

    context, preview_row, runtime_env_override = _build_scenario_preview_context(
        scenario,
        runtime_options=runtime_options,
        initial_context=initial_context,
    )
    stop_on_failure = bool(getattr(scenario, "stop_on_failure", True))
    prerequisite_results = []
    blocked = False
    blocked_reason = ""

    def execute_one(step, index: int):
        test_case = _step_test_case(step)
        base_config = _case_to_dict(test_case)
        if runtime_env_override:
            base_config["environment_id"] = runtime_env_override.get("environment_id")
            base_config["environment_base_url"] = runtime_env_override.get("environment_base_url")
            base_config["environment_variables"] = copy.deepcopy(runtime_env_override.get("environment_variables") or {})
        if not context.get("__globals_loaded"):
            context.update(_load_global_variables(base_config.get("project_id")))
            context["__globals_loaded"] = True
        merged_config = _merge_case_config(base_config, _step_value(step, "overrides") or {})
        pre_processor_logs = _run_processors(
            _step_value(step, "pre_processors"),
            phase="pre",
            context=context,
            response=None,
            response_json=None,
            project_id=base_config.get("project_id"),
            environment_id=base_config.get("environment_id"),
        )
        env_context = _resolve_environment_variables(copy.deepcopy(base_config.get("environment_variables") or {}))
        render_context = {}
        render_context.update(env_context)
        render_context.update(context)
        rendered_config = _render_value(merged_config, render_context)

        pre_ok, pre_details = _evaluate_rules(
            _step_value(step, "preconditions"), response=None, response_json=None, context=context, phase="precondition"
        )
        if not pre_ok:
            payload = {
                "step_index": index,
                "step_id": _step_value(step, "id"),
                "step_order": _step_value(step, "step_order", index + 1),
                "step_name": _step_value(step, "step_name") or f"步骤{index + 1}",
                "test_case_id": getattr(test_case, "id", None),
                "test_case_name": getattr(test_case, "name", ""),
                "request": {
                    "method": rendered_config.get("method"),
                    "base_url": rendered_config.get("base_url"),
                    "path": rendered_config.get("path"),
                    "params": rendered_config.get("params"),
                    "headers": rendered_config.get("headers"),
                    "body_json": rendered_config.get("body_json"),
                    "body_text": rendered_config.get("body_text"),
                },
                "preconditions": pre_details,
                "pre_processors": pre_processor_logs,
                "result": {
                    "success": 0,
                    "status_code": None,
                    "response_time_ms": 0,
                    "error_message": "preconditions failed",
                    "response_body": None,
                    "assertion_result": "preconditions failed",
                },
                "extracted": {},
                "assertions": _build_step_assertion_summary(rendered_config, []),
                "post_processors": [],
                "unresolved_placeholders": sorted(_collect_unresolved_placeholders(rendered_config)),
            }
            return payload, False, "preconditions failed"

        exec_result, response_json, response = execute_runtime_case(rendered_config)
        post_processor_logs = _run_processors(
            _step_value(step, "post_processors"),
            phase="post",
            context=context,
            response=response,
            response_json=response_json,
            project_id=base_config.get("project_id"),
            environment_id=base_config.get("environment_id"),
        )
        extracted = (
            _extract_context_vars(_step_value(step, "extract_rules"), response, response_json, context=context)
            if response
            else {}
        )
        context.update(extracted)
        context["__last_response"] = {
            "status_code": response.status_code if response is not None else None,
            "headers": dict(response.headers) if response is not None else {},
            "cookies": dict(response.cookies) if response is not None else {},
            "text": response.text if response is not None else "",
            "json": response_json,
        }
        custom_assert_ok, custom_assert_details = _evaluate_rules(
            _step_value(step, "assertions"),
            response=response,
            response_json=response_json,
            context=context,
            phase="assertion",
        )
        if _step_value(step, "assertions"):
            native_ok = bool(exec_result.get("success"))
            final_ok = native_ok and custom_assert_ok
            exec_result["success"] = 1 if final_ok else 0
            extra = f" | custom assertions: {'PASS' if custom_assert_ok else 'FAIL'}"
            exec_result["assertion_result"] = (exec_result.get("assertion_result") or "") + extra
        assertion_summary = _build_step_assertion_summary(rendered_config, custom_assert_details)
        step_payload = {
            "step_index": index,
            "step_id": _step_value(step, "id"),
            "step_order": _step_value(step, "step_order", index + 1),
            "step_name": _step_value(step, "step_name") or f"步骤{index + 1}",
            "test_case_id": getattr(test_case, "id", None),
            "test_case_name": getattr(test_case, "name", ""),
            "request": exec_result.get("request")
            or {
                "method": rendered_config.get("method"),
                "base_url": rendered_config.get("base_url"),
                "path": rendered_config.get("path"),
                "params": rendered_config.get("params"),
                "headers": rendered_config.get("headers"),
                "body_json": rendered_config.get("body_json"),
                "body_text": rendered_config.get("body_text"),
            },
            "preconditions": pre_details,
            "pre_processors": pre_processor_logs,
            "result": {key: value for key, value in exec_result.items() if key != "request"},
            "extracted": extracted,
            "assertions": assertion_summary,
            "post_processors": post_processor_logs,
            "unresolved_placeholders": sorted(_collect_unresolved_placeholders(rendered_config)),
        }
        return step_payload, bool(exec_result.get("success")), exec_result.get("error_message") or ""

    if include_previous:
        for index, step in enumerate((steps or [])[:step_index]):
            if not bool(_step_value(step, "enabled", True)):
                continue
            step_payload, ok, error_message = execute_one(step, index)
            prerequisite_results.append(
                {
                    "step_index": index,
                    "step_id": step_payload.get("step_id"),
                    "step_name": step_payload.get("step_name"),
                    "success": ok,
                    "error_message": error_message,
                }
            )
            if not ok and stop_on_failure and not bool(_step_value(step, "continue_on_fail", False)):
                blocked = True
                blocked_reason = error_message or "previous step failed"
                break

    target_step = (steps or [])[step_index]
    if blocked:
        target_preview = preview_scenario_steps(
            scenario,
            [target_step],
            runtime_options=runtime_options,
            initial_context=context,
        ).get("steps", [])
        target_payload = target_preview[0] if target_preview else {"step_index": step_index}
        return {
            "summary": {
                "step_index": step_index,
                "include_previous": include_previous,
                "blocked": True,
                "blocked_reason": blocked_reason,
                "preview_row": preview_row,
            },
            "prerequisite_results": prerequisite_results,
            "step_result": target_payload,
            "context_snapshot": {key: value for key, value in context.items() if not str(key).startswith("__")},
        }

    step_payload, ok, error_message = execute_one(target_step, step_index)
    return {
        "summary": {
            "step_index": step_index,
            "include_previous": include_previous,
            "blocked": False,
            "success": ok,
            "error_message": error_message or "",
            "preview_row": preview_row,
        },
        "prerequisite_results": prerequisite_results,
        "step_result": step_payload,
        "context_snapshot": {key: value for key, value in context.items() if not str(key).startswith("__")},
    }


def _json_path_get_legacy(data, path: str):
    if path.startswith("$."):
        path = path[2:]
    path = path.replace("[", ".").replace("]", "")
    current = data
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(current, list):
            idx = int(part)
            current = current[idx]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(part)
    return current


def _json_path_get(data, path: str):
    raw_path = str(path or "").strip()
    if not raw_path:
        return data

    # Prefer a standard JSONPath engine first (supports filters like ?(@.x == 'y')).
    if jsonpath_parse is not None:
        try:
            compiled = _JSONPATH_CACHE.get(raw_path)
            if compiled is None:
                compiled = jsonpath_parse(raw_path)
                _JSONPATH_CACHE[raw_path] = compiled
            matches = compiled.find(data)
            if not matches:
                raise KeyError(raw_path)
            values = [match.value for match in matches]
            return values[0] if len(values) == 1 else values
        except Exception:  # noqa: BLE001
            # Fall back to legacy parser for backward compatibility.
            pass

    return _json_path_get_legacy(data, raw_path)


def _extract_text_regex(text: str, regex: str, group: int = 1):
    match = re.search(regex, text or "")
    if not match:
        return None
    try:
        return match.group(group)
    except Exception:
        return match.group(0)


def _resolve_rule_value(rule: dict, *, response=None, response_json=None, context=None):
    context = context or {}
    source = rule.get("source") or rule.get("from") or "context"

    if "literal" in rule:
        return _render_value(rule.get("literal"), context)
    if "value" in rule and source == "literal":
        return _render_value(rule.get("value"), context)

    if source == "context":
        var_name = rule.get("var") or rule.get("path")
        return context.get(var_name)
    if source == "status_code":
        return None if response is None else response.status_code
    if source == "headers":
        if response is None:
            return None
        header_name = rule.get("header") or rule.get("path")
        if not header_name:
            return dict(response.headers)
        value = response.headers.get(header_name)
        regex = rule.get("regex")
        if regex:
            return _extract_text_regex(value or "", regex, int(rule.get("group", 1)))
        return value
    if source == "body_text":
        if response is None:
            return None
        text = response.text
        regex = rule.get("regex")
        if regex:
            return _extract_text_regex(text, regex, int(rule.get("group", 1)))
        return text
    if source == "body_json":
        if response_json is None:
            return None
        path = rule.get("jsonpath") or rule.get("path")
        if not path:
            return response_json
        return _json_path_get(response_json, str(path))
    return None


def _compare(op: str, actual, expected):
    if op == "exists":
        return actual is not None
    if op == "not_exists":
        return actual is None
    if op == "not_empty":
        return actual not in (None, "", [], {}, ())
    if op == "empty":
        return actual in (None, "", [], {}, ())
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "contains":
        return False if actual is None else str(expected) in str(actual)
    if op == "not_contains":
        return False if actual is None else str(expected) not in str(actual)
    if op in {"gt", "ge", "lt", "le"}:
        try:
            a = float(actual)
            b = float(expected)
        except Exception:
            return False
        if op == "gt":
            return a > b
        if op == "ge":
            return a >= b
        if op == "lt":
            return a < b
        return a <= b
    return False


def _evaluate_rules(rules, *, response=None, response_json=None, context=None, phase="assertion"):
    if not isinstance(rules, list) or not rules:
        return True, []
    passed = True
    details = []
    context = context or {}

    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            continue
        try:
            op = str(rule.get("op") or "eq")
            actual = _resolve_rule_value(rule, response=response, response_json=response_json, context=context)
            expected = _render_value(rule.get("expected"), context) if "expected" in rule else None
            ok = _compare(op, actual, expected)
            passed = passed and ok
            details.append(
                {
                    "index": idx,
                    "name": rule.get("name") or f"{phase}-{idx}",
                    "op": op,
                    "actual": actual,
                    "expected": expected,
                    "pass": ok,
                }
            )
        except Exception as exc:  # noqa: BLE001
            passed = False
            details.append(
                {
                    "index": idx,
                    "name": rule.get("name") or f"{phase}-{idx}",
                    "op": rule.get("op"),
                    "pass": False,
                    "error": str(exc),
                }
            )
    return passed, details


def _extract_context_vars(rules, response, response_json, context=None):
    extracted = {}
    if not isinstance(rules, list):
        return extracted

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        var_name = rule.get("var") or rule.get("name")
        if not var_name:
            continue
        try:
            value = _resolve_rule_value(
                {
                    "source": rule.get("from", "body_json"),
                    "path": rule.get("path"),
                    "jsonpath": rule.get("jsonpath"),
                    "header": rule.get("header"),
                    "regex": rule.get("regex"),
                    "group": rule.get("group", 1),
                },
                response=response,
                response_json=response_json,
                context=context or {},
            )
            extracted[var_name] = value
        except Exception:
            continue
    return extracted


def _run_processors(
    processors,
    *,
    phase: str,
    context: dict,
    response=None,
    response_json=None,
    project_id=None,
    environment_id=None,
):
    if not isinstance(processors, list):
        return []

    last_response = context.get("__last_response") if isinstance(context, dict) else None
    runtime_response = response
    runtime_response_json = response_json
    if runtime_response is None and isinstance(last_response, dict):
        runtime_response_json = last_response.get("json")

    logs = []
    for idx, item in enumerate(processors, start=1):
        if not isinstance(item, dict):
            continue
        p_type = str(item.get("type") or "").strip().lower()
        target = str(item.get("target") or item.get("var") or "").strip()
        name = item.get("name") or f"{phase}-{idx}"
        if not p_type:
            logs.append({"index": idx, "name": name, "pass": False, "error": "processor type is required"})
            continue
        try:
            if p_type == "set_var":
                if not target:
                    raise ValueError("target is required")
                value = _render_value(item.get("value"), context)
                context[target] = value
                logs.append(
                    {
                        "index": idx,
                        "name": name,
                        "type": p_type,
                        "target": target,
                        "value": context.get(target),
                        "pass": True,
                    }
                )
                continue

            if p_type == "timestamp":
                if not target:
                    raise ValueError("target is required")
                is_ms = bool(item.get("ms"))
                context[target] = int(time.time() * 1000) if is_ms else int(time.time())
                logs.append(
                    {
                        "index": idx,
                        "name": name,
                        "type": p_type,
                        "target": target,
                        "value": context.get(target),
                        "pass": True,
                    }
                )
                continue

            if p_type == "datetime":
                if not target:
                    raise ValueError("target is required")
                fmt = str(item.get("format") or "%Y-%m-%d %H:%M:%S")
                context[target] = datetime.now().strftime(fmt)
                logs.append(
                    {
                        "index": idx,
                        "name": name,
                        "type": p_type,
                        "target": target,
                        "value": context.get(target),
                        "pass": True,
                    }
                )
                continue

            if p_type == "random_phone":
                if not target:
                    raise ValueError("target is required")
                context[target] = _resolve_builtin_value("phone_cn")
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": True})
                continue

            if p_type == "uuid":
                if not target:
                    raise ValueError("target is required")
                import uuid  # local import to avoid global unused import

                context[target] = str(uuid.uuid4())
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": True})
                continue

            if p_type == "transform":
                if not target:
                    raise ValueError("target is required")
                op = str(item.get("op") or "").strip()
                if not op:
                    raise ValueError("op is required")
                raw_value = _render_value(item.get("value"), context)
                arg = item.get("arg")
                context[target] = _apply_transform(raw_value, op, arg, context)
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "op": op, "pass": True})
                continue

            if p_type == "extract_var":
                if phase != "post":
                    raise ValueError("extract_var can only be used in post processor")
                if not target:
                    raise ValueError("target is required")
                var_type = str(item.get("variable_type") or item.get("var_type") or "temp").strip().lower()
                extract_from = str(item.get("extract_from") or item.get("source") or "response_json").strip().lower()
                extract_scope = str(item.get("extract_scope") or item.get("scope") or "whole").strip().lower()
                extract_expr = str(item.get("extract_expr") or item.get("jsonpath") or item.get("path") or "").strip()
                if extract_scope != "whole" and not extract_expr:
                    raise ValueError("extract_expr is required when extract_scope is not whole")
                use_expr = bool(extract_expr)
                value = None

                if extract_from == "response_json":
                    parsed_json = runtime_response_json
                    if parsed_json is None and runtime_response is not None:
                        parsed_json = _safe_parse_json(runtime_response.text)
                    if use_expr and parsed_json is not None:
                        value = _json_path_get(parsed_json, extract_expr)
                    elif extract_scope == "whole":
                        value = parsed_json
                    elif parsed_json is not None:
                        value = _json_path_get(parsed_json, extract_expr)
                elif extract_from == "response_text":
                    text = runtime_response.text if runtime_response is not None else (
                        last_response.get("text") if isinstance(last_response, dict) else ""
                    )
                    if use_expr:
                        matched = re.search(extract_expr, text or "")
                        if matched:
                            value = matched.group(1) if matched.groups() else matched.group(0)
                    elif extract_scope == "whole":
                        value = text
                elif extract_from == "response_xml":
                    xml_text = runtime_response.text if runtime_response is not None else (
                        last_response.get("text") if isinstance(last_response, dict) else ""
                    )
                    if use_expr and xml_text:
                        root = ET.fromstring(xml_text)
                        node = root.find(extract_expr)
                        if node is not None:
                            value = node.text
                    elif extract_scope == "whole":
                        value = xml_text
                elif extract_from == "response_header":
                    headers = {}
                    if runtime_response is not None:
                        headers = dict(runtime_response.headers)
                    elif isinstance(last_response, dict):
                        headers = last_response.get("headers") or {}
                    if use_expr:
                        value = headers.get(extract_expr)
                    elif extract_scope == "whole":
                        value = headers
                    else:
                        value = headers.get(extract_expr)
                elif extract_from == "response_cookie":
                    cookies = {}
                    if runtime_response is not None:
                        cookies = dict(runtime_response.cookies)
                    elif isinstance(last_response, dict):
                        cookies = last_response.get("cookies") or {}
                    if use_expr:
                        value = cookies.get(extract_expr)
                    elif extract_scope == "whole":
                        value = cookies
                    else:
                        value = cookies.get(extract_expr)
                else:
                    raise ValueError(f"unsupported extract_from: {extract_from}")

                context[target] = value if value is not None else item.get("default")
                if var_type == "global":
                    context.setdefault("__global__", {})[target] = context[target]
                elif var_type == "environment":
                    context.setdefault("__environment__", {})[target] = context[target]
                _persist_runtime_variable(
                    var_type=var_type,
                    target=target,
                    value=context[target],
                    project_id=project_id,
                    environment_id=environment_id,
                )
                logs.append(
                    {
                        "index": idx,
                        "name": name,
                        "type": p_type,
                        "target": target,
                        "value": context.get(target),
                        "variable_type": var_type,
                        "extract_from": extract_from,
                        "extract_scope": extract_scope,
                        "pass": True,
                    }
                )
                continue

            if p_type == "json_extract":
                if phase != "post":
                    raise ValueError("json_extract can only be used in post processor")
                if not target:
                    raise ValueError("target is required")
                path = str(item.get("jsonpath") or item.get("path") or "").strip()
                if not path:
                    raise ValueError("jsonpath is required")
                if runtime_response_json is None:
                    context[target] = item.get("default")
                else:
                    try:
                        context[target] = _json_path_get(runtime_response_json, path)
                    except Exception:
                        context[target] = item.get("default")
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": True})
                continue

            if p_type == "regex_extract":
                if phase != "post":
                    raise ValueError("regex_extract can only be used in post processor")
                if not target:
                    raise ValueError("target is required")
                pattern = str(item.get("pattern") or item.get("regex") or "")
                if not pattern:
                    raise ValueError("pattern is required")
                source = str(item.get("source") or "body_text").strip().lower()
                group = int(item.get("group") or 1)
                if source == "headers" and runtime_response is not None:
                    raw = json.dumps(dict(runtime_response.headers), ensure_ascii=False)
                elif source == "status_code" and runtime_response is not None:
                    raw = str(runtime_response.status_code)
                else:
                    raw = runtime_response.text if runtime_response is not None else (
                        last_response.get("text") if isinstance(last_response, dict) else ""
                    )
                value = _extract_text_regex(raw, pattern, group)
                context[target] = value if value is not None else item.get("default")
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": True})
                continue

            if p_type == "header_extract":
                if phase != "post":
                    raise ValueError("header_extract can only be used in post processor")
                if not target:
                    raise ValueError("target is required")
                header = str(item.get("header") or item.get("path") or "").strip()
                if not header:
                    raise ValueError("header is required")
                if runtime_response is not None:
                    context[target] = runtime_response.headers.get(header)
                elif isinstance(last_response, dict):
                    context[target] = (last_response.get("headers") or {}).get(header, item.get("default"))
                else:
                    context[target] = item.get("default")
                logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": True})
                continue

            raise ValueError(f"unsupported processor type: {p_type}")
        except Exception as exc:  # noqa: BLE001
            logs.append({"index": idx, "name": name, "type": p_type, "target": target, "pass": False, "error": str(exc)})
    return logs


def execute_runtime_case(case_config: dict) -> Tuple[dict, Optional[object], Optional[httpx.Response]]:
    request_info, rendered_config, _context_vars = _prepare_runtime_case(case_config)
    start = time.perf_counter()
    try:
        with httpx.Client(
            timeout=int(case_config.get("timeout_seconds") or 10),
            verify=bool(case_config.get("verify_ssl", True)),
        ) as client:
            response = client.request(
                method=str(rendered_config.get("method") or "GET").upper(),
                url=request_info.get("url"),
                headers=rendered_config.get("headers"),
                params=rendered_config.get("params"),
                json=rendered_config.get("body_json"),
                content=rendered_config.get("body_text") if rendered_config.get("body_json") is None else None,
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        checks = []
        success = True

        try:
            response_json = response.json()
        except Exception:
            response_json = _safe_parse_json(response.text)

        assert_status = case_config.get("assert_status")
        if assert_status is not None:
            ok = response.status_code == int(assert_status)
            checks.append(f"status == {assert_status}: {'PASS' if ok else 'FAIL'}")
            success = success and ok

        assert_contains = case_config.get("assert_contains")
        if assert_contains:
            ok = str(assert_contains) in response.text
            checks.append(f"body contains '{assert_contains}': {'PASS' if ok else 'FAIL'}")
            success = success and ok

        custom_rules = case_config.get("custom_assertions")
        custom_ok, custom_details = _evaluate_rules(
            custom_rules,
            response=response,
            response_json=response_json,
            context={},
            phase="assertion",
        )
        if isinstance(custom_rules, list) and custom_rules:
            passed_count = sum(1 for item in custom_details if item.get("pass"))
            checks.append(
                f"custom assertions {passed_count}/{len(custom_details)}: {'PASS' if custom_ok else 'FAIL'}"
            )
            success = success and custom_ok

        if not checks:
            checks.append("no assertions configured")

        result = {
            "success": 1 if success else 0,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "error_message": None,
            "request": request_info,
            "response_headers": dict(response.headers),
            "response_content_type": response.headers.get("content-type"),
            "response_body": response.text,
            "assertion_result": " | ".join(checks),
        }
        return result, response_json, response
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        message = str(exc)[:255]
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            message = "HTTPS 证书校验失败（自签名证书）。请在接口配置中关闭“SSL 证书校验”后重试。"
        result = {
            "success": 0,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error_message": message,
            "request": request_info,
            "response_headers": None,
            "response_content_type": None,
            "response_body": None,
            "assertion_result": "request execution failed",
        }
        return result, None, None


def execute_test_case(test_case: TestCase) -> dict:
    # 单接口执行：渲染变量 -> 发送请求 -> 执行断言 -> 返回可落库结果。
    result, _, _ = execute_runtime_case(_case_to_dict(test_case))
    return result


def _build_step_assertion_summary(rendered_config: dict, scenario_assert_details) -> list:
    summary = []
    if rendered_config.get("assert_status") is not None:
        summary.append(
            {
                "source": "接口断言",
                "rule": "status_code",
                "expected": rendered_config.get("assert_status"),
            }
        )
    if rendered_config.get("assert_contains"):
        summary.append(
            {
                "source": "接口断言",
                "rule": "response_body_contains",
                "expected": rendered_config.get("assert_contains"),
            }
        )
    custom_rules = rendered_config.get("custom_assertions")
    if custom_rules not in (None, "", [], {}):
        summary.append(
            {
                "source": "接口断言",
                "rule": "custom_assertions",
                "expected": custom_rules,
            }
        )
    for detail in scenario_assert_details or []:
        if isinstance(detail, dict):
            item = dict(detail)
            item.setdefault("source", "场景断言")
            summary.append(item)
        else:
            summary.append({"source": "场景断言", "detail": detail})
    return summary


def _normalize_data_set_assert_targets(targets) -> list:
    if not isinstance(targets, list):
        return []
    allowed = {"status_code", "request_headers", "response_body"}
    result = []
    for item in targets:
        key = str(item or "").strip().lower()
        if key in allowed and key not in result:
            result.append(key)
    return result


def _evaluate_data_set_assertions(assert_config, step_results: list, context: Optional[dict] = None) -> tuple:
    if not isinstance(assert_config, dict) or not bool(assert_config.get("assert_enabled", False)):
        return True, []

    render_context = context if isinstance(context, dict) else {}
    targets = _normalize_data_set_assert_targets(assert_config.get("assert_targets"))
    if not targets:
        return False, [{"target": "config", "pass": False, "detail": "dataset assertions enabled but no targets configured"}]
    if not step_results:
        return False, [{"target": "runtime", "pass": False, "detail": "no step results for dataset assertions"}]

    last_step = step_results[-1] if isinstance(step_results[-1], dict) else {}
    result_payload = last_step.get("result") if isinstance(last_step.get("result"), dict) else {}
    request_payload = last_step.get("request") if isinstance(last_step.get("request"), dict) else {}

    details = []
    overall = True

    def _render_expected(raw):
        rendered = _render_value(str(raw or ""), render_context)
        return str(rendered).strip()

    if "status_code" in targets:
        expected = assert_config.get("assert_status_code")
        actual = result_payload.get("status_code")
        ok = expected is not None and actual is not None and int(actual) == int(expected)
        details.append(
            {
                "target": "status_code",
                "pass": bool(ok),
                "expected": expected,
                "actual": actual,
                "detail": f"status_code expected={expected}, actual={actual}",
            }
        )
        overall = overall and bool(ok)

    if "request_headers" in targets:
        jsonpath = _render_expected(assert_config.get("assert_header_jsonpath", "") or "")
        expected = _render_expected(assert_config.get("assert_header_expected", "") or "")
        header_data = request_payload.get("headers") if isinstance(request_payload.get("headers"), dict) else {}
        actual = None
        if jsonpath:
            try:
                actual = _json_path_get(header_data, jsonpath)
            except Exception:
                actual = None
        ok = jsonpath != "" and expected != "" and str(actual if actual is not None else "") == expected
        details.append(
            {
                "target": "request_headers",
                "pass": bool(ok),
                "jsonpath": jsonpath,
                "expected": expected,
                "actual": actual,
                "detail": f"request_headers path={jsonpath}, expected={expected}, actual={actual}",
            }
        )
        overall = overall and bool(ok)

    if "response_body" in targets:
        jsonpath = _render_expected(assert_config.get("assert_response_jsonpath", "") or "")
        expected = _render_expected(assert_config.get("assert_response_expected", "") or "")
        body_text = result_payload.get("response_body")
        response_json = _safe_parse_json(body_text if isinstance(body_text, str) else "")
        actual = None
        if jsonpath and response_json is not None:
            try:
                actual = _json_path_get(response_json, jsonpath)
            except Exception:
                actual = None
        ok = jsonpath != "" and expected != "" and str(actual if actual is not None else "") == expected
        details.append(
            {
                "target": "response_body",
                "pass": bool(ok),
                "jsonpath": jsonpath,
                "expected": expected,
                "actual": actual,
                "detail": f"response_body path={jsonpath}, expected={expected}, actual={actual}",
            }
        )
        overall = overall and bool(ok)

    return overall, details


def _execute_scenario_steps(scenario: TestScenario, context: dict, runtime_env_override: Optional[dict] = None) -> tuple:
    step_results = []
    overall_success = True
    error_message = None
    steps = scenario.steps.filter(enabled=True).select_related("test_case").order_by("step_order", "id")
    for step in steps:
        step: ScenarioStep
        base_config = _case_to_dict(step.test_case)
        if runtime_env_override:
            base_config["environment_id"] = runtime_env_override.get("environment_id")
            base_config["environment_base_url"] = runtime_env_override.get("environment_base_url")
            base_config["environment_variables"] = copy.deepcopy(runtime_env_override.get("environment_variables") or {})
        if not context.get("__globals_loaded"):
            context.update(_load_global_variables(base_config.get("project_id")))
            context["__globals_loaded"] = True
        merged_config = _merge_case_config(base_config, step.overrides or {})
        pre_processor_logs = _run_processors(
            step.pre_processors,
            phase="pre",
            context=context,
            response=None,
            response_json=None,
            project_id=base_config.get("project_id"),
            environment_id=base_config.get("environment_id"),
        )
        env_context = _resolve_environment_variables(copy.deepcopy(base_config.get("environment_variables") or {}))
        render_context = {}
        render_context.update(env_context)
        render_context.update(context)
        rendered_config = _render_value(merged_config, render_context)

        pre_ok, pre_details = _evaluate_rules(
            step.preconditions, response=None, response_json=None, context=context, phase="precondition"
        )
        if not pre_ok:
            assertion_summary = _build_step_assertion_summary(rendered_config, [])
            exec_result = {
                "success": 0,
                "status_code": None,
                "response_time_ms": 0,
                "error_message": "preconditions failed",
                "response_body": None,
                "assertion_result": "preconditions failed",
            }
            step_results.append(
                {
                    "step_id": step.id,
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "test_case_id": step.test_case_id,
                    "test_case_name": step.test_case.name,
                    "request": {
                        "method": rendered_config.get("method"),
                        "base_url": rendered_config.get("base_url"),
                        "path": rendered_config.get("path"),
                        "params": rendered_config.get("params"),
                        "headers": rendered_config.get("headers"),
                        "body_json": rendered_config.get("body_json"),
                        "body_text": rendered_config.get("body_text"),
                    },
                    "preconditions": pre_details,
                    "pre_processors": pre_processor_logs,
                    "result": exec_result,
                    "extracted": {},
                    "assertions": assertion_summary,
                    "post_processors": [],
                }
            )
            overall_success = False
            error_message = "preconditions failed"
            if scenario.stop_on_failure and not step.continue_on_fail:
                break
            continue

        exec_result, response_json, response = execute_runtime_case(rendered_config)
        post_processor_logs = _run_processors(
            step.post_processors,
            phase="post",
            context=context,
            response=response,
            response_json=response_json,
            project_id=base_config.get("project_id"),
            environment_id=base_config.get("environment_id"),
        )
        extracted = (
            _extract_context_vars(step.extract_rules, response, response_json, context=context)
            if response
            else {}
        )
        context.update(extracted)
        context["__last_response"] = {
            "status_code": response.status_code if response is not None else None,
            "headers": dict(response.headers) if response is not None else {},
            "cookies": dict(response.cookies) if response is not None else {},
            "text": response.text if response is not None else "",
            "json": response_json,
        }
        custom_assert_ok, custom_assert_details = _evaluate_rules(
            step.assertions,
            response=response,
            response_json=response_json,
            context=context,
            phase="assertion",
        )
        if step.assertions:
            native_ok = bool(exec_result.get("success"))
            final_ok = native_ok and custom_assert_ok
            exec_result["success"] = 1 if final_ok else 0
            extra = f" | custom assertions: {'PASS' if custom_assert_ok else 'FAIL'}"
            exec_result["assertion_result"] = (exec_result.get("assertion_result") or "") + extra
        assertion_summary = _build_step_assertion_summary(rendered_config, custom_assert_details)

        step_success = bool(exec_result.get("success"))
        step_result_payload = copy.deepcopy(exec_result)
        if isinstance(step_result_payload, dict):
            step_result_payload.pop("request", None)
        step_results.append(
            {
                "step_id": step.id,
                "step_order": step.step_order,
                "step_name": step.step_name,
                "test_case_id": step.test_case_id,
                "test_case_name": step.test_case.name,
                "request": exec_result.get("request")
                or {
                    "method": rendered_config.get("method"),
                    "base_url": rendered_config.get("base_url"),
                    "path": rendered_config.get("path"),
                    "params": rendered_config.get("params"),
                    "headers": rendered_config.get("headers"),
                    "body_json": rendered_config.get("body_json"),
                    "body_text": rendered_config.get("body_text"),
                },
                "preconditions": pre_details,
                "pre_processors": pre_processor_logs,
                "result": step_result_payload,
                "extracted": extracted,
                "assertions": assertion_summary,
                "post_processors": post_processor_logs,
            }
        )
        if not step_success:
            overall_success = False
            error_message = exec_result.get("error_message") or "step failed"
            if scenario.stop_on_failure and not step.continue_on_fail:
                break
    return overall_success, step_results, error_message


def execute_scenario(
    scenario: TestScenario,
    initial_context: Optional[dict] = None,
    runtime_options: Optional[dict] = None,
) -> dict:
    # 场景执行：按步骤串行运行，并在共享上下文中传递提取变量。
    start = time.perf_counter()
    base_context: dict = dict(initial_context or {})
    # Carry context across rows so successful extraction in earlier rows
    # can be reused by later rows / downstream scenarios.
    carry_context: dict = dict(base_context)
    iterations = []
    merged_step_results = []
    overall_success = True
    error_messages = []

    runtime_param_enabled = (runtime_options or {}).get("param_enabled")
    scenario_param_enabled = bool(getattr(scenario, "param_enabled", False))
    param_enabled = scenario_param_enabled if runtime_param_enabled is not False else False

    data_rows = []
    if param_enabled and getattr(scenario, "data_set_id", None):
        data_rows = _parse_data_set_rows(getattr(scenario, "data_set", None))
        data_rows = _pick_data_rows(
            data_rows,
            str(getattr(scenario, "data_mode", "all") or "all"),
            getattr(scenario, "data_pick", None),
            runtime_options=runtime_options,
        )
    if not data_rows:
        data_rows = [{}]

    retry_count = int(getattr(scenario, "param_retry_count", 0) or 0)
    runtime_retry = (runtime_options or {}).get("param_retry_count")
    if runtime_retry is not None:
        try:
            retry_count = int(runtime_retry)
        except (TypeError, ValueError):
            retry_count = int(getattr(scenario, "param_retry_count", 0) or 0)
    retry_count = max(0, min(retry_count, 10))
    runtime_env_override = _resolve_runtime_environment_override(scenario, runtime_options)

    row_context = dict(carry_context)
    for index, row in enumerate(data_rows, start=1):
        row_data = _normalize_data_row(row)
        row_assert_config = row_data.pop("__assertions__", None)
        attempt = 0
        iter_success = False
        iter_steps = []
        iter_error = None
        iter_duration = 0

        while attempt <= retry_count:
            attempt += 1
            row_context = dict(carry_context)
            row_context["row"] = row_data
            for key, value in row_data.items():
                row_context[str(key)] = value
            iter_start = time.perf_counter()
            iter_success, iter_steps, iter_error = _execute_scenario_steps(
                scenario,
                row_context,
                runtime_env_override=runtime_env_override,
            )
            data_set = getattr(scenario, "data_set", None)
            default_assert_config = {
                "assert_enabled": bool(getattr(data_set, "assert_enabled", False)) if data_set is not None else False,
                "assert_targets": getattr(data_set, "assert_targets", None) if data_set is not None else [],
                "assert_status_code": getattr(data_set, "assert_status_code", None) if data_set is not None else None,
                "assert_header_jsonpath": getattr(data_set, "assert_header_jsonpath", None) if data_set is not None else None,
                "assert_header_expected": getattr(data_set, "assert_header_expected", None) if data_set is not None else None,
                "assert_response_jsonpath": getattr(data_set, "assert_response_jsonpath", None) if data_set is not None else None,
                "assert_response_expected": getattr(data_set, "assert_response_expected", None) if data_set is not None else None,
            }
            active_assert_config = row_assert_config if isinstance(row_assert_config, dict) else default_assert_config
            data_set_assert_ok, data_set_assertions = _evaluate_data_set_assertions(
                active_assert_config,
                iter_steps,
                context=row_context,
            )
            if data_set_assertions:
                if iter_steps and isinstance(iter_steps[-1], dict):
                    iter_steps[-1]["data_set_assertions"] = data_set_assertions
                    assertion_items = list(iter_steps[-1].get("assertions") or [])
                    for detail in data_set_assertions:
                        assertion_items.append(
                            {
                                "source": "dataset_assertion",
                                "detail": detail.get("detail"),
                                "pass": detail.get("pass"),
                            }
                        )
                    iter_steps[-1]["assertions"] = assertion_items
            if not data_set_assert_ok:
                iter_success = False
                fail_text = "; ".join(
                    [str(item.get("detail") or "").strip() for item in data_set_assertions if not item.get("pass")]
                )
                iter_error = fail_text or iter_error or "dataset assertions failed"
                if iter_steps and isinstance(iter_steps[-1], dict):
                    step_result = iter_steps[-1].get("result")
                    if isinstance(step_result, dict):
                        step_result["success"] = 0
                        current_assertion_result = str(step_result.get("assertion_result") or "").strip()
                        suffix = " | dataset assertions: FAIL"
                        step_result["assertion_result"] = (
                            f"{current_assertion_result}{suffix}" if current_assertion_result else "dataset assertions: FAIL"
                        )
            iter_duration = int((time.perf_counter() - iter_start) * 1000)
            if iter_success:
                # Persist latest successful runtime variables for next rows/scenarios.
                # Keep extracted/runtime vars, but do not let row payload overwrite carry context.
                for k, v in row_context.items():
                    if str(k).startswith("__") or k == "row" or k in row_data:
                        continue
                    carry_context[k] = v
                break

        iterations.append(
            {
                "iteration_index": index,
                "row_data": row_data,
                "success": 1 if iter_success else 0,
                "duration_ms": iter_duration,
                "attempt_count": attempt,
                "results": iter_steps,
                "data_set_assertions": (
                    iter_steps[-1].get("data_set_assertions")
                    if iter_steps and isinstance(iter_steps[-1], dict)
                    else []
                ),
                "error_message": iter_error,
            }
        )

        if not iter_success:
            overall_success = False
            if iter_error:
                error_messages.append(f"row {index}: {iter_error}")

        for step in iter_steps:
            merged = dict(step)
            merged["iteration_index"] = index
            merged["row_data"] = row_data
            merged_step_results.append(merged)

    duration_ms = int((time.perf_counter() - start) * 1000)
    snapshot = {k: v for k, v in carry_context.items() if not str(k).startswith("__")}
    return {
        "success": 1 if overall_success else 0,
        "duration_ms": duration_ms,
        "results": merged_step_results,
        "iterations": iterations,
        "context_snapshot": snapshot,
        "error_message": " | ".join(error_messages)[:255] if error_messages else None,
    }
