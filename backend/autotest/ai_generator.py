# 作者: lxl
# 说明: 业务模块实现。
import json
import os
from typing import Any, Optional

import httpx


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("模型未返回可解析内容")
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: try to parse the first JSON object/array block embedded in text.
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(cleaned):
            if ch not in "[{":
                continue
            try:
                obj, _ = decoder.raw_decode(cleaned[idx:])
                return obj
            except json.JSONDecodeError:
                continue
        raise ValueError("模型返回内容不是有效 JSON，请重试或调整提示词")


def _normalize_cases(data: Any) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        data = data["cases"]
    if not isinstance(data, list):
        raise ValueError("模型返回格式错误：需要 JSON 数组或 {cases: []}")

    normalized = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "name": item.get("name") or f"AI生成用例{idx}",
                "description": item.get("description") or "AI 自动生成",
                "base_url": item.get("base_url") or "",
                "path": item.get("path") or "/",
                "method": str(item.get("method") or "GET").upper(),
                "headers": item.get("headers") if isinstance(item.get("headers"), (dict, list)) else None,
                "params": item.get("params") if isinstance(item.get("params"), (dict, list)) else None,
                "body_json": item.get("body_json") if isinstance(item.get("body_json"), (dict, list)) else None,
                "body_text": item.get("body_text"),
                "timeout_seconds": int(item.get("timeout_seconds") or 10),
                "assert_status": item.get("assert_status"),
                "assert_contains": item.get("assert_contains"),
            }
        )
    return normalized


def _parse_json_response(resp: httpx.Response, *, scene: str) -> Any:
    try:
        return resp.json()
    except (ValueError, json.JSONDecodeError):
        preview = (resp.text or "").strip().replace("\n", " ").replace("\r", " ")
        if len(preview) > 180:
            preview = preview[:180] + "..."
        raise ValueError(
            f"{scene}返回非 JSON（status={resp.status_code}）。"
            f"请检查 AI Base URL 是否为 .../v1。响应片段: {preview or '<empty>'}"
        )


def _candidate_base_urls(base_url: str) -> list[str]:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        return []
    items = [normalized]
    if not normalized.endswith("/v1"):
        items.append(normalized + "/v1")
    dedup = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def _extract_content_from_chat(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    msg = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = msg.get("content") if isinstance(msg, dict) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _extract_content_from_responses(data: dict) -> str:
    if isinstance(data.get("output_text"), str) and data.get("output_text").strip():
        return data["output_text"].strip()
    output = data.get("output")
    if not isinstance(output, list):
        return ""
    parts = []
    for block in output:
        if not isinstance(block, dict):
            continue
        content = block.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
    return "\n".join(parts).strip()


def _invoke_model_text(*, base_url: str, api_key: str, model: str, timeout: int, system_prompt: str, user_prompt: str):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error = None
    with httpx.Client(timeout=timeout) as client:
        for candidate in _candidate_base_urls(base_url):
            # Try chat/completions first.
            try:
                chat_resp = client.post(
                    f"{candidate}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                    },
                )
                chat_resp.raise_for_status()
                chat_data = _parse_json_response(chat_resp, scene="AI 接口")
                if isinstance(chat_data, dict):
                    content = _extract_content_from_chat(chat_data)
                    if content:
                        return content, "chat_completions", candidate
            except Exception as exc:  # noqa: BLE001
                last_error = exc

            # Fallback: responses API.
            try:
                resp = client.post(
                    f"{candidate}/responses",
                    headers=headers,
                    json={
                        "model": model,
                        "instructions": system_prompt,
                        "input": user_prompt,
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                data = _parse_json_response(resp, scene="AI 接口")
                if isinstance(data, dict):
                    content = _extract_content_from_responses(data)
                    if content:
                        return content, "responses", candidate
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

    if isinstance(last_error, Exception):
        raise last_error
    raise ValueError("AI 接口调用失败，请检查 AI Base URL / API Key / 模型名称")


def generate_test_cases_by_ai(
    user_prompt: str,
    base_url_hint: Optional[str] = None,
    *,
    ai_base_url: Optional[str] = None,
    ai_api_key: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_timeout_seconds: Optional[int] = None,
) -> dict:
    base_url = str(ai_base_url or os.getenv("AI_BASE_URL", "https://api.openai.com/v1")).strip().rstrip("/")
    api_key = str(ai_api_key or os.getenv("AI_API_KEY", "")).strip()
    model = str(ai_model or os.getenv("AI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout = int(ai_timeout_seconds or int(os.getenv("AI_TIMEOUT_SECONDS", "60")))

    if not api_key:
        raise ValueError("AI_API_KEY 未配置")

    system_prompt = (
        "你是接口自动化测试专家。请根据用户描述生成接口测试用例。"
        "仅返回 JSON，不要解释。"
        "返回格式为数组，数组元素字段包括："
        "name, description, base_url, path, method, headers, params, body_json, body_text, "
        "timeout_seconds, assert_status, assert_contains。"
        "headers/params/body_json 使用 JSON 对象；无值可为 null。"
    )
    if base_url_hint:
        system_prompt += f" 优先使用这个基础地址: {base_url_hint}。"

    content, _, _ = _invoke_model_text(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    if not content:
        raise ValueError("模型未返回内容")

    parsed = _extract_json(content)
    cases = _normalize_cases(parsed)
    return {"cases": cases, "raw_content": content}


def generate_test_cases_from_openapi_summary(
    summary: dict,
    extra_requirements: Optional[str] = None,
    *,
    ai_base_url: Optional[str] = None,
    ai_api_key: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_timeout_seconds: Optional[int] = None,
) -> dict:
    base_url_hint = summary.get("base_url")
    op_count = summary.get("operation_count", 0)
    title = summary.get("title") or "OpenAPI"

    user_prompt = (
        f"请根据以下 OpenAPI 摘要生成接口自动化测试用例。\n"
        f"文档标题: {title}\n"
        f"接口数量: {op_count}\n"
        f"基础地址: {base_url_hint or '未知'}\n"
        "请覆盖典型成功场景、常见参数错误场景、未授权场景（若需要鉴权）、分页/查询场景（如适用）。\n"
        "优先为每个核心接口至少生成1条用例。\n"
        "OpenAPI 摘要(JSON):\n"
        f"{json.dumps(summary, ensure_ascii=False)}"
    )
    if extra_requirements:
        user_prompt += f"\n额外要求:\n{extra_requirements}"
    return generate_test_cases_by_ai(
        user_prompt=user_prompt,
        base_url_hint=base_url_hint,
        ai_base_url=ai_base_url,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
        ai_timeout_seconds=ai_timeout_seconds,
    )


def validate_ai_connection(
    *,
    ai_base_url: Optional[str] = None,
    ai_api_key: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_timeout_seconds: Optional[int] = None,
) -> dict:
    base_url = str(ai_base_url or os.getenv("AI_BASE_URL", "https://api.openai.com/v1")).strip().rstrip("/")
    api_key = str(ai_api_key or os.getenv("AI_API_KEY", "")).strip()
    model = str(ai_model or os.getenv("AI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout = int(ai_timeout_seconds or int(os.getenv("AI_TIMEOUT_SECONDS", "60")))

    if not api_key:
        raise ValueError("AI_API_KEY 未配置")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        # Prefer listing models first (cheap and fast). Some OpenAI-compatible
        # providers do not implement /models, so we fallback to a tiny completion.
        try:
            resp = client.get(f"{base_url}/models", headers=headers)
            resp.raise_for_status()
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, json.JSONDecodeError):
                data = None
            if not isinstance(data, dict):
                raise ValueError("models endpoint not json")
            model_ids = []
            for item in (data.get("data") if isinstance(data, dict) else []) or []:
                if isinstance(item, dict) and item.get("id"):
                    model_ids.append(str(item["id"]))
            return {
                "ok": True,
                "base_url": base_url,
                "model": model,
                "model_count": len(model_ids),
                "model_exists": (model in model_ids) if model_ids else None,
                "check_mode": "models",
            }
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {404, 405}:
                raise
        except ValueError:
            # /models may return non-json content on some providers; fallback below
            pass

        # Fallback: probe both chat/responses styles and both base_url + base_url/v1.
        _invoke_model_text(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
            system_prompt="You are a helpful assistant.",
            user_prompt="ping",
        )
        return {
            "ok": True,
            "base_url": base_url,
            "model": model,
            "model_count": None,
            "model_exists": None,
            "check_mode": "completion_probe",
        }
