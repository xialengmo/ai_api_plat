// 作者: lxl
// 说明: 前端业务逻辑模块。
export function blankForm() {
  return {
    id: null,
    name: "",
    description: "",
    base_url: "",
    path: "",
    method: "GET",
    headers_text: "",
    params_text: "",
    body_json_text: "",
    body_text: "",
    timeout_seconds: 1,
    verify_ssl: false,
    environment: null,
    module: null,
    assert_enabled: false,
    assert_status: 200,
    assert_contains: "",
    custom_assertions_text: ""
  };
}

export function formatJsonText(value) {
  if (value === null || value === undefined || value === "") return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function parseOptionalJson(text, fieldName) {
  if (!text || !String(text).trim()) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${fieldName} 不是合法 JSON`);
  }
}

export function caseToForm(item) {
  const assertEnabled = Boolean(
    item.assert_status !== null && item.assert_status !== undefined
    || String(item.assert_contains || "").trim()
    || (Array.isArray(item.custom_assertions) && item.custom_assertions.length)
  );
  return {
    id: item.id ?? null,
    name: item.name ?? "",
    description: item.description ?? "",
    base_url: item.base_url ?? "",
    path: item.path ?? "",
    method: (item.method || "GET").toUpperCase(),
    headers_text: formatJsonText(item.headers),
    params_text: formatJsonText(item.params),
    body_json_text: formatJsonText(item.body_json),
    body_text: item.body_text ?? "",
    timeout_seconds: item.timeout_seconds ?? 1,
    verify_ssl: item.verify_ssl ?? false,
    environment: item.environment ?? null,
    module: item.module ?? null,
    assert_enabled: assertEnabled,
    assert_status: item.assert_status ?? "",
    assert_contains: item.assert_contains ?? "",
    custom_assertions_text: formatJsonText(item.custom_assertions)
  };
}

export function formToPayload(form) {
  if (!form.name?.trim()) throw new Error("接口名称不能为空");
  if (!form.base_url?.trim() || !form.path?.trim()) throw new Error("Base URL 和 Path 不能为空");
  if (!/^https?:\/\//i.test(form.base_url.trim())) {
    throw new Error("Base URL 必须以 http:// 或 https:// 开头");
  }

  const customAssertions = parseOptionalJson(form.custom_assertions_text, "高级断言");
  if (customAssertions !== null && !Array.isArray(customAssertions)) {
    throw new Error("高级断言必须是 JSON 数组");
  }

  const toNullableId = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const raw = typeof value === "object" ? (value.id ?? value.value ?? null) : value;
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  };

  const assertEnabled = Boolean(form.assert_enabled);
  return {
    name: form.name.trim(),
    description: form.description?.trim() || null,
    base_url: form.base_url.trim(),
    path: form.path.trim(),
    method: (form.method || "GET").toUpperCase(),
    headers: parseOptionalJson(form.headers_text, "Headers"),
    params: parseOptionalJson(form.params_text, "Query Params"),
    body_json: parseOptionalJson(form.body_json_text, "Body JSON"),
    body_text: form.body_text || null,
    timeout_seconds: Number(form.timeout_seconds || 1),
    verify_ssl: Boolean(form.verify_ssl),
    environment: toNullableId(form.environment),
    module: toNullableId(form.module),
    assert_status: assertEnabled
      ? (form.assert_status === "" || form.assert_status === null ? null : Number(form.assert_status))
      : null,
    assert_contains: assertEnabled ? (form.assert_contains?.trim() || null) : null,
    custom_assertions: assertEnabled ? customAssertions : null
  };
}
