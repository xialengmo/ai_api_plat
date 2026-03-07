# 作者: lxl
# 说明: OpenAPI 文档解析与摘要提取。
import json
from typing import Any, Optional

import httpx


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _try_parse_json(text: str) -> dict[str, Any]:
    return json.loads(text)


def _try_parse_simple_yaml(text: str) -> dict[str, Any]:
    # JSON 解析失败时再尝试 YAML，确保同一入口兼容两种格式。

    try:
        import yaml  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ValueError("当前未安装 PyYAML，无法解析 YAML 文档，请改为 JSON 或安装 PyYAML") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("OpenAPI 文档格式无效")
    return data


def load_openapi_document(
    schema_url: Optional[str] = None, schema_text: Optional[str] = None
) -> dict[str, Any]:
    # 支持 URL 拉取和文本直传两种入口，统一返回字典结构。
    if schema_url:
        with httpx.Client(timeout=30) as client:
            resp = client.get(schema_url)
            resp.raise_for_status()
            raw = resp.text
    elif schema_text:
        raw = schema_text
    else:
        raise ValueError("schema_url 和 schema_text 至少提供一个")

    try:
        data = _try_parse_json(raw)
    except Exception:
        data = _try_parse_simple_yaml(raw)

    if not isinstance(data, dict):
        raise ValueError("OpenAPI 文档格式无效")
    if "paths" not in data:
        raise ValueError("未找到 OpenAPI paths 字段")
    return data


def _resolve_ref(node: Any, root: dict[str, Any], depth: int = 0) -> Any:
    # 递归展开 $ref（仅支持文档内引用），并限制深度避免循环引用。
    if depth > 12 or not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not ref or not isinstance(ref, str):
        return node
    if not ref.startswith("#/"):
        return node
    current: Any = root
    try:
        for part in ref[2:].split("/"):
            current = current[part]
    except Exception:  # noqa: BLE001
        return node
    return _resolve_ref(current, root, depth + 1)


def _schema_to_example(schema: Any, root: dict[str, Any], depth: int = 0) -> Any:
    # 尽量生成可执行的示例值，优先 example/default/enum，再按类型兜底。
    if depth > 8:
        return None
    schema = _resolve_ref(schema, root, depth)
    if not isinstance(schema, dict):
        return None

    if schema.get("example") is not None:
        return schema.get("example")
    if schema.get("default") is not None:
        return schema.get("default")
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]

    for key in ("oneOf", "anyOf", "allOf"):
        arr = schema.get(key)
        if isinstance(arr, list) and arr:
            sample = _schema_to_example(arr[0], root, depth + 1)
            if sample is not None:
                return sample

    schema_type = str(schema.get("type") or "").lower()
    if schema_type == "object" or ("properties" in schema):
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        result = {}
        for k, v in props.items():
            result[str(k)] = _schema_to_example(v, root, depth + 1)
        if not result:
            additional = schema.get("additionalProperties")
            if isinstance(additional, dict):
                result["key"] = _schema_to_example(additional, root, depth + 1)
        return result
    if schema_type == "array":
        item_schema = schema.get("items")
        return [_schema_to_example(item_schema, root, depth + 1)]
    if schema_type in {"integer", "number"}:
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        fmt = str(schema.get("format") or "").lower()
        if fmt in {"date-time", "datetime"}:
            return "2026-01-01T00:00:00Z"
        if fmt == "date":
            return "2026-01-01"
        if fmt in {"email"}:
            return "demo@example.com"
        if fmt in {"uuid"}:
            return "00000000-0000-0000-0000-000000000000"
        return ""
    return None


def _extract_media_example(media: Any, root: dict[str, Any]) -> Any:
    if not isinstance(media, dict):
        return None
    if media.get("example") is not None:
        return media.get("example")
    examples = media.get("examples")
    if isinstance(examples, dict):
        for item in examples.values():
            if isinstance(item, dict) and item.get("value") is not None:
                return item.get("value")
    schema = media.get("schema")
    return _schema_to_example(schema, root)


def _extract_request_body(rb: Any, root: dict[str, Any]) -> dict[str, Any]:
    rb = _resolve_ref(rb, root)
    if not isinstance(rb, dict):
        return {"required": False, "content_types": []}
    content = rb.get("content") if isinstance(rb.get("content"), dict) else {}
    content_types = list(content.keys())
    json_ct = None
    for ct in content_types:
        ct_lower = str(ct).lower()
        if "json" in ct_lower or ct_lower.endswith("+json"):
            json_ct = ct
            break
    json_example = None
    if json_ct:
        json_example = _extract_media_example(content.get(json_ct), root)
    return {
        "required": bool(rb.get("required")),
        "content_types": content_types[:8],
        "json_content_type": json_ct,
        "json_example": json_example,
    }


def summarize_openapi_document(doc: dict[str, Any]) -> dict[str, Any]:
    # 生成结构化摘要，供 AI 提示词和本地 fallback 生成逻辑共用。
    info = doc.get("info") or {}
    servers = doc.get("servers") or []
    base_url = None
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict):
            base_url = first.get("url")

    paths = doc.get("paths") or {}
    operations: list[dict[str, Any]] = []

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_params = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
        for method, op in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                continue

            params = []
            all_params = []
            if isinstance(path_params, list):
                all_params.extend(path_params)
            if isinstance(op.get("parameters"), list):
                all_params.extend(op["parameters"])

            for raw_p in all_params:
                p = _resolve_ref(raw_p, doc)
                if not isinstance(p, dict):
                    continue
                schema = _resolve_ref(p.get("schema"), doc)
                if not isinstance(schema, dict):
                    schema = {}
                p_example = p.get("example")
                if p_example is None:
                    p_example = _schema_to_example(schema, doc)
                params.append(
                    {
                        "name": p.get("name"),
                        "in": p.get("in"),
                        "required": bool(p.get("required")),
                        "type": schema.get("type"),
                        "example": p_example,
                        "description": p.get("description"),
                    }
                )

            request_body = _extract_request_body(op.get("requestBody"), doc)

            responses = []
            raw_responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
            for code, resp in list(raw_responses.items())[:6]:
                resolved_resp = _resolve_ref(resp, doc)
                if isinstance(resolved_resp, dict):
                    responses.append(
                        {
                            "code": str(code),
                            "description": resolved_resp.get("description"),
                            "content_types": list((resolved_resp.get("content") or {}).keys())[:4]
                            if isinstance(resolved_resp.get("content"), dict)
                            else [],
                        }
                    )

            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": op.get("operationId"),
                    "summary": op.get("summary"),
                    "description": op.get("description"),
                    "tags": op.get("tags") if isinstance(op.get("tags"), list) else [],
                    "parameters": params[:40],
                    "request_body": request_body,
                    "responses": responses,
                }
            )

    return {
        "title": info.get("title"),
        "version": info.get("version"),
        "description": info.get("description"),
        "base_url": base_url,
        "operation_count": len(operations),
        "operations": operations,
    }
