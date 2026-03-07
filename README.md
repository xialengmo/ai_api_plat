# 接口自动化测试平台（前后端分离）

一个最小可运行的接口自动化测试平台示例：

- 前端：`Vue3 + Vite`
- 后端：`Django + Django REST Framework`
- 数据库：`MySQL`

功能包含：

- 接口管理（增删改查）
- 单接口执行（按配置发起 HTTP 请求）
- 多接口场景串联执行（上下游参数传递）
- 断言校验（状态码、响应体包含文本）
- 执行历史记录

## 目录结构

```text
ai_plat/
├─ backend/                # Django 后端
├─ frontend/               # Vue 前端
├─ sql/init_mysql.sql      # MySQL 初始化 SQL
└─ docker-compose.yml      # MySQL 容器（可选）
```

## 1. 启动 MySQL

方式 A：使用 Docker（推荐）

```bash
docker compose up -d mysql
```

方式 B：本地 MySQL 手工执行

```sql
source sql/init_mysql.sql;
```

## 2. 启动后端（Django）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

后端地址：`http://127.0.0.1:8000`

可访问接口示例：

- 健康检查：`GET http://127.0.0.1:8000/api/health`
- 接口列表：`GET http://127.0.0.1:8000/api/test-cases`
- 场景列表：`GET http://127.0.0.1:8000/api/scenarios`
- 场景执行：`POST http://127.0.0.1:8000/api/scenarios/{id}/run`
- AI 生成用例：`POST http://127.0.0.1:8000/api/ai/generate-test-cases`
- OpenAPI 文档生成用例：`POST http://127.0.0.1:8000/api/ai/generate-from-openapi`

### AI 大模型配置（OpenAI 兼容协议）

在 `backend/.env` 中配置：

```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的Key
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=60
```

也可替换为其他 OpenAI 兼容服务（如部分国产模型网关），只需修改 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`。

### Swagger / OpenAPI 文档生成用例

前端已支持两种输入方式：

- 文档 URL（例如 `https://example.com/openapi.json`）
- 粘贴 OpenAPI 文档文本（JSON/YAML）

后端接口：

```http
POST /api/ai/generate-from-openapi
Content-Type: application/json
```

请求示例：

```json
{
  "schema_url": "https://petstore3.swagger.io/api/v3/openapi.json",
  "extra_requirements": "增加分页参数异常和鉴权失败场景"
}
```

或：

```json
{
  "schema_text": "{\"openapi\":\"3.0.0\",\"paths\":{...}}"
}
```

## 3. 启动前端（Vue）

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 使用说明

1. 在“接口管理”模块维护接口定义（Base URL、Path、Method、Headers、Params 等）
2. 在“自动化测试 > 单接口执行”中选择接口直接执行
3. 在“自动化测试 > 多接口场景串联”中编排步骤并执行场景
4. 可在步骤 `overrides` 中用 `{{变量名}}` 引用前置步骤提取的变量
5. 在步骤 `extract_rules` 中定义响应变量提取规则（如 token、sku_id）
6. 切换到“AI生成用例”模块，输入业务描述或 OpenAPI 文档自动生成接口定义

### 场景串联配置示例（购物流程）

步骤1（登录）提取 token：

```json
[
  { "var": "token", "from": "body_json", "path": "data.token" }
]
```

也支持从响应头和正文正则提取：

```json
[
  { "var": "trace_id", "from": "headers", "header": "X-Trace-Id" },
  { "var": "csrf", "from": "body_text", "regex": "csrf=(\\w+)", "group": 1 }
]
```

步骤2（搜索商品）覆盖请求并提取 sku_id：

```json
{
  "headers": { "Authorization": "Bearer {{token}}" },
  "params": { "keyword": "手机" }
}
```

```json
[
  { "var": "sku_id", "from": "body_json", "path": "data.list.0.skuId" }
]
```

步骤3（下单购买）使用上下游变量：

```json
{
  "headers": { "Authorization": "Bearer {{token}}" },
  "body_json": { "skuId": "{{sku_id}}", "count": 1 }
}
```

### 前置条件与断言编排（金额校验 / 库存校验）

每个场景步骤可配置：

- `preconditions`：请求发出前先判断上下文变量是否满足条件
- `assertions`：收到响应后执行业务断言（金额、库存、数量、状态等）

支持的常用 `op`：

- `eq` `ne`
- `gt` `ge` `lt` `le`
- `contains` `not_contains`
- `exists` `not_exists`
- `empty` `not_empty`

支持的数据源：

- `context`（上下文变量）
- `status_code`
- `headers`（配 `header`）
- `body_text`（可配 `regex`）
- `body_json`（配 `jsonpath` 或 `path`）

前置条件示例（执行搜索前必须已拿到 token）：

```json
[
  { "name": "token存在", "source": "context", "var": "token", "op": "not_empty" }
]
```

业务断言示例（库存、金额）：

```json
[
  { "name": "库存大于0", "source": "body_json", "jsonpath": "$.data.stock", "op": "gt", "expected": 0 },
  { "name": "订单金额大于0", "source": "body_json", "jsonpath": "$.data.amount", "op": "gt", "expected": 0 }
]
```

### JSONPath / path 说明

- 推荐使用 `jsonpath`：如 `$.data.list[0].skuId`
- 兼容简写 `path`：如 `data.list.0.skuId`

## 数据表说明

- `test_cases`：接口用例配置
- `run_histories`：执行历史
- `test_scenarios`：场景配置
- `scenario_steps`：场景步骤
- `scenario_run_histories`：场景执行历史

## 可扩展方向

- 测试套件 / 批量执行
- 环境变量管理（dev/test/prod）
- 鉴权（Token 登录、RBAC）
- 响应 JSONPath 断言
- 定时任务执行与报告导出
- pytest 集成与 CI/CD
