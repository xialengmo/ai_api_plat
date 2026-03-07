# 接口自动化测试与监控平台

一个前后端分离的接口测试工作台，覆盖接口资产管理、单接口执行、场景编排、数据集参数化、AI 辅助生成、项目级权限控制，以及监控平台接入与资源可视化。

- 前端：`Vue 3` + `Vite` + `Element Plus` + `ECharts`
- 后端：`Django 5` + `Django REST Framework`
- 数据库：`MySQL`
- HTTP/解析能力：`httpx`、`PyYAML`、`jsonpath-ng`
- 远程部署/监控能力：`paramiko`

## 核心能力

### 1. 工作台与项目空间

- 仪表盘总览：展示接口数、场景数、执行总量、通过/失败数、平均耗时、近 7 天趋势。
- 最近执行与失败热点：可查看最近运行记录、最近失败记录、耗时 Top 接口、失败 Top 服务/接口。
- 多项目隔离：支持项目切换，不同项目下的接口、场景、环境、数据集彼此隔离。
- 模块化资产管理：接口、场景、数据集均可挂载到模块，支持树形模块组织。

### 2. 接口资产管理

- 接口定义 CRUD：维护名称、方法、路径、Header、Query、JSON Body、Text Body。
- 环境绑定：接口可绑定项目环境，自动带入 `base_url`、环境变量、默认 Header。
- 断言能力：支持状态码断言、响应内容包含断言，以及可视化/JSON 高级断言。
- 执行控制：支持超时设置、SSL 校验开关。
- 运行前预检：可预览实际请求 URL、Header、参数、Body、断言和未解析占位符。
- 单接口快速执行：执行后自动写入历史，保留请求快照、响应头、响应体、耗时与断言结果。

### 3. 场景编排与自动化执行

- 多步骤场景：将多个接口编排为完整业务流程。
- 步骤覆盖：每个步骤都可覆盖请求参数、Header、Body。
- 变量提取：支持从响应 JSON、响应头、正文正则中提取变量。
- 前置条件与业务断言：支持在步骤执行前做条件判断，执行后做金额/库存/状态等业务断言。
- 失败控制：支持场景级 `stop_on_failure` 和步骤级 `continue_on_fail`。
- 单步调试与场景预检：支持场景预检、批量预检、单步运行时调试。
- 批量执行：支持按模块批量执行场景、批量运行已选场景、场景排序调整。
- 执行报告：保留步骤结果、迭代结果、上下文快照、总耗时、失败原因。

### 4. 数据集参数化

- 数据集管理：支持表格型数据集和原始文本数据。
- 场景参数化：场景可关联数据集，按 `all` / `random` / 指定行号区间等模式执行。
- 行级重试：支持参数化重试次数配置。
- 数据断言：数据集可配置状态码、Header、响应 JSON 等断言目标。
- 行变量注入：执行时可通过 `{{row.xxx}}` 引用当前数据行字段。

### 5. 环境与变量体系

- 项目环境：可为每个项目配置多个环境，如开发、测试、预发、生产影子环境。
- 默认 Header：环境可统一注入鉴权头、租户头等固定请求头。
- 环境变量：支持自定义变量与内置变量。
- 内置变量：已内置时间戳、日期、日期时间、手机号等动态值生成能力。
- 全局变量：后端支持项目级全局变量，运行时参与渲染。
- 表达式渲染：支持环境变量变换与拼接，例如 `&token|base64`、`&appid+&timestamp|md5`。

### 6. AI 助手与文档导入

- 业务描述生成接口草稿：输入业务描述后自动生成接口定义草稿。
- OpenAPI 导入：支持通过 OpenAPI/Swagger 文档 URL 或直接粘贴 JSON/YAML 文本生成接口草稿。
- 导入预览：保存前可预览即将导入的接口列表。
- 去重策略：导入时支持按策略处理重复接口。
- 连通性校验：支持保存前校验 AI 配置是否可用。
- 待评审队列：仪表盘可显示 AI 生成但尚未评审的草稿提醒。

### 7. 权限、用户与审计

- 登录鉴权：使用签名 Token，前端以 `Bearer Token` 调用后端接口。
- 默认管理员：首次登录时会自动创建管理员账号，便于本地快速体验。
- 用户管理：`admin` 可创建、编辑、禁用用户并重置密码。
- 按项目授权：`admin` 可访问全部项目，普通用户仅能访问授权项目。
- 登录审计：记录登录成功/失败、来源 IP、User-Agent。
- 操作审计：自动记录 `POST` / `PUT` / `PATCH` / `DELETE` 类变更操作。

### 8. 监控平台与资源看板

- 监控平台管理：支持创建监控平台并配置 SSH、部署方式、Prometheus / Grafana / Alertmanager 地址。
- 在线部署与离线包上传：支持一键部署，也支持上传离线监控包后部署。
- 单机/主机集群：支持单机监控与多目标主机监控。
- 目标主机管理：可维护多个监控目标及端口。
- 指标采集：支持读取最新指标与历史趋势。
- 资源总览：前端可视化展示 API QPS、P95、5xx、网络流量、CPU/内存、连接数、Redis 命中率、容器/Pod 异常等指标。

## 目录结构

```text
ai_plat/
├─ backend/                   # Django 后端
│  ├─ autotest/               # 业务模型、执行器、视图、监控逻辑
│  ├─ config/                 # Django 配置
│  ├─ manage.py
│  └─ requirements.txt
├─ frontend/                  # Vue 前端
│  ├─ src/
│  │  ├─ components/          # 页面组件
│  │  ├─ api.js               # 前端 API 封装
│  │  └─ App.vue              # 主页面
│  └─ package.json
├─ sql/init_mysql.sql         # MySQL 初始化脚本
├─ docker-compose.yml         # MySQL 容器编排
└─ README.md
```

## 快速开始

## 1. 准备环境

建议环境：

- `Python 3.11+`
- `Node.js 18+`
- `MySQL 8+`
- 可选：`Docker Desktop`

## 2. 启动 MySQL

方式 A：使用 Docker（推荐）

```bash
docker compose up -d mysql
```

方式 B：本地 MySQL 手工初始化

```sql
source sql/init_mysql.sql;
```

## 3. 启动后端

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

可用接口示例：

- 健康检查：`GET /api/health`
- 登录：`POST /api/auth/login`
- 项目列表：`GET /api/projects`
- 接口列表：`GET /api/test-cases`
- 场景列表：`GET /api/scenarios`
- 场景执行：`POST /api/scenarios/{id}/run`
- AI 生成：`POST /api/ai/generate-test-cases`
- OpenAPI 导入：`POST /api/ai/generate-from-openapi`
- 权限总览：`GET /api/rbac/overview`
- 监控平台：`GET /api/monitor/platforms`

## 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 5. 初始化登录

系统在首次登录时会自动确保存在管理员账号。默认值如下：

- 用户名：`admin`
- 密码：`admin123456`

首次登录后请立即修改密码。

也可以在 `backend/.env` 中通过以下环境变量自定义：

```env
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123456
DEFAULT_ADMIN_EMAIL=
AUTH_TOKEN_TTL_SECONDS=259200
```

## 后端配置示例

`backend/.env` 基本配置如下：

```env
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

DB_NAME=api_test_platform
DB_USER=root
DB_PASSWORD=123456
DB_HOST=127.0.0.1
DB_PORT=3306

AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=60
```

## 推荐使用流程

1. 进入“项目管理”，先创建项目。
2. 为项目创建“环境”，配置环境地址、默认 Header、环境变量。
3. 在“接口管理”中创建模块并维护接口资产。
4. 对单接口进行“预检”或“快速执行”，确认请求配置正确。
5. 在“自动化测试”中编排场景步骤，配置变量提取、前置条件、业务断言。
6. 如需参数化回放，为场景绑定数据集并设置执行模式。
7. 在“场景报告”与“执行历史”中查看步骤明细、上下文快照和错误原因。
8. 需要批量建模时，使用“AI 助手”通过业务描述或 OpenAPI 文档生成草稿并导入。
9. 如需多人协作，使用“权限与审计”页面管理成员与项目授权。
10. 如需查看机器/服务指标，在“监控配置”和“资源监控”中接入监控平台。

## 变量与占位符说明

### 1. 场景上下文变量

步骤之间可通过 `{{变量名}}` 传递值，例如：

```json
{
  "headers": {
    "Authorization": "Bearer {{token}}"
  }
}
```

### 2. 数据集当前行变量

参数化场景中可引用当前数据行：

```json
{
  "body_json": {
    "username": "{{row.username}}",
    "password": "{{row.password}}"
  }
}
```

### 3. 环境/全局变量表达式

支持环境变量引用和简单转换：

- 单变量：`&token|base64`
- 拼接后转换：`&appid+&timestamp|md5`
- 内置变量示例：`timestamp_int`、`timestamp_ms`、`date_ymd`、`datetime`、`phone_cn`

### 4. 变量提取示例

从登录接口提取 `token`：

```json
[
  { "var": "token", "from": "body_json", "path": "data.token" }
]
```

从响应头或正文提取变量：

```json
[
  { "var": "trace_id", "from": "headers", "header": "X-Trace-Id" },
  { "var": "csrf", "from": "body_text", "regex": "csrf=(\\w+)", "group": 1 }
]
```

## 常用接口分组

### 认证与用户

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- `GET/POST /api/auth/users`
- `PUT/DELETE /api/auth/users/{id}`

### 项目与资产

- `GET/POST /api/projects`
- `GET/PUT/DELETE /api/projects/{id}`
- `GET/POST /api/modules`
- `GET/PUT/DELETE /api/modules/{id}`
- `GET/POST /api/test-cases`
- `GET/PUT/DELETE /api/test-cases/{id}`
- `POST /api/test-cases/preview`
- `POST /api/test-cases/{id}/run`

### 场景与报告

- `GET/POST /api/scenarios`
- `GET/PUT/DELETE /api/scenarios/{id}`
- `POST /api/scenarios/preview`
- `POST /api/scenarios/preview-batch`
- `POST /api/scenarios/debug-step`
- `POST /api/scenarios/run-batch`
- `POST /api/scenarios/reorder`
- `POST /api/scenarios/{id}/run`
- `GET /api/scenario-run-histories`

### 数据集与环境

- `GET/POST /api/data-sets`
- `GET/PUT/DELETE /api/data-sets/{id}`
- `GET/POST /api/environments`
- `GET/PUT/DELETE /api/environments/{id}`

### AI 与导入

- `POST /api/ai/validate-config`
- `POST /api/ai/generate-test-cases`
- `POST /api/ai/generate-from-openapi`

### 监控与权限

- `GET /api/dashboard/summary`
- `GET /api/rbac/overview`
- `GET/POST /api/monitor/platforms`
- `POST /api/monitor/platforms/{id}/deploy`
- `POST /api/monitor/platforms/{id}/upload-package`
- `GET /api/monitor/platforms/{id}/status`
- `GET /api/monitor/platforms/{id}/logs`
- `GET /api/monitor/platforms/{id}/targets`
- `GET /api/monitor/platforms/{id}/metrics/latest`
- `GET /api/monitor/platforms/{id}/metrics/history`

## 监控功能说明

监控管理操作仅允许管理员执行。典型流程如下：

1. 在“监控配置”中新建监控平台，填写主机、SSH 账号密码、部署方式。
2. 选择在线部署，或上传离线包后部署。
3. 根据平台类型配置单机或多个目标主机。
4. 部署成功后，在“资源监控”页面查看最新指标和历史趋势。

## 适用场景

- 接口测试平台原型验证
- 团队内部测试资产管理
- 接口回归与场景串联测试
- OpenAPI 文档快速建模
- 小型项目的项目级权限控制与审计留痕
- 将接口测试与主机/服务资源监控放在同一工作台中统一查看

## 后续可扩展方向

- 定时任务/调度执行
- 更完整的测试套件模型
- 更细粒度的角色权限模型
- AI 草稿审批流
- 更丰富的断言模板与数据工厂能力

