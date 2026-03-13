# 接口自动化测试与监控平台

一个前后端分离的接口测试与监控平台，覆盖接口资产管理、单接口执行、场景编排、数据集参数化、AI 辅助生成、项目级权限控制，以及监控平台接入与资源可视化。

- 前端：`Vue 3` + `Vite` + `Element Plus` + `ECharts`
- 后端：`Django 4.2` + `Django REST Framework`
- 数据库：`MySQL`
- HTTP / 解析能力：`httpx`、`PyYAML`、`jsonpath-ng`
- 远程部署 / 监控接入 / 容器化：`paramiko`、`gunicorn`、`nginx`、`Docker Compose`

## 核心能力

### 1. 工作台与项目空间

- 仪表盘总览：展示接口数、场景数、执行总量、通过 / 失败数、平均耗时、近 7 天趋势
- 最近执行与失败热点：查看最近运行记录、失败记录、耗时 Top 接口、失败 Top 服务 / 接口
- 多项目隔离：不同项目下的接口、场景、环境、数据集彼此隔离
- 模块化资产管理：接口、场景、数据集均可挂载到模块下，支持树形模块组织

### 2. 接口资产管理

- 接口定义 CRUD：维护名称、方法、路径、Header、Query、JSON Body、Text Body
- 环境绑定：接口可绑定项目环境，自动带入 `base_url`、环境变量、默认 Header
- 断言能力：支持状态码断言、响应内容包含断言，以及 JSON 结构断言
- 执行控制：支持超时设置、SSL 校验开关
- 运行前预检：可预览实际请求 URL、Header、参数、Body、断言和未解析占位符
- 单接口快速执行：执行后自动写入历史，保留请求快照、响应头、响应体、耗时与断言结果

### 3. 场景编排与自动化执行

- 多步骤场景：将多个接口编排为完整业务流程
- 步骤级覆盖：每一步都可覆盖请求参数、Header、Body
- 变量提取：支持从响应 JSON、响应头、正文正则中提取变量
- 前置条件与业务断言：支持执行前判断、执行后做业务结果断言
- 失败控制：支持场景级 `stop_on_failure` 与步骤级 `continue_on_fail`
- 单步调试与场景预检：支持场景预检、批量预检、单步运行时调试
- 批量执行：支持按模块批量执行场景、批量运行已选场景、场景排序调整
- 执行报告：保留步骤结果、迭代结果、上下文快照、总耗时、失败原因

### 4. 数据集参数化

- 数据集管理：支持表格型数据集和原始文本数据
- 场景参数化：场景可关联数据集，按 `all` / `random` / 指定行号范围等模式执行
- 行级重试：支持参数化重试次数配置
- 数据断言：数据集可配置状态码、Header、响应 JSON 等断言目标
- 行变量注入：运行时可通过 `{{row.xxx}}` 引用当前数据行字段

### 5. 环境与变量体系

- 项目环境：每个项目可配置多个环境，如开发、测试、预发、生产影子环境
- 默认 Header：环境可统一注入鉴权头、租户头等固定请求头
- 环境变量：支持自定义变量与内置变量
- 内置变量：已内置时间戳、日期、日期时间、手机号等动态值生成能力
- 全局变量：后端支持项目级全局变量，运行时参与渲染
- 表达式渲染：支持环境变量转换与拼接，例如 `&token|base64`、`&appid+&timestamp|md5`

### 6. 权限与审计

- 用户登录、登出、修改密码
- 用户管理与项目授权
- 登录审计与操作审计
- 管理员视角的权限总览

### 7. AI 辅助生成

- 根据业务描述生成测试用例草稿
- 导入 OpenAPI 文档后自动生成测试用例
- AI 配置校验，便于对接兼容 OpenAI 的接口

### 8. 监控平台接入

- Docker 运行时检测：保存或部署前可检测目标机的 SSH、Docker、Compose 与引擎访问状态
- 监控平台配置、在线部署、离线包部署、部署日志查看、状态检查
- 已有监控栈复用：检测到目标机已存在 Prometheus / Alertmanager / Exporter 时优先复用并刷新采集配置
- Docker / Compose 自愈：缺失时自动安装，常见证书或软件源异常时尝试自动纠错
- 目标主机管理：支持单机与主机集群模式，自动生成 Prometheus 抓取目标
- 最新指标与历史趋势查询

### 9. 部署与交付

- Linux 一键部署：提供 `deploy/linux_oneclick.sh`，同时支持联网安装与离线包部署
- Docker 微服务部署：提供 `db`、`backend`、`frontend`、`nginx` 四容器编排模板
- Docker 单镜像部署：提供 `Dockerfile.single`，由同一镜像内的 `nginx + gunicorn` 对外提供完整应用
- 容器启动入口：后端容器自动等待数据库、执行 `migrate`、`collectstatic` 并通过 `gunicorn` 对外提供服务

## 快速开始

## 1. 准备环境

建议环境：

- `Python 3.11+`（推荐 `Python 3.13`）
- `Node.js 18+`
- `MySQL 5.7+`（推荐 `MySQL 8+`；项目内置 `MySQL 5.7` 兼容模式）
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

# MySQL 5.7
powershell -ExecutionPolicy Bypass -File .\use-mysql57.ps1

# MySQL 8+
# powershell -ExecutionPolicy Bypass -File .\use-mysql8.ps1

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

## 5. 初始登录

系统在首次登录时会自动确保存在管理员账号，默认值如下：

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

## 6. 后端配置示例

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
DB_MYSQL57_COMPAT=False
# DB_ENGINE=django.db.backends.mysql

DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123456
DEFAULT_ADMIN_EMAIL=
AUTH_TOKEN_TTL_SECONDS=259200

AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=60
```

## 7. MySQL / Django 兼容说明

- 当前项目依赖默认锁定为 `Django 4.2.x`，用于兼容 `MySQL 5.7`
- 使用 `MySQL 5.7` 时，可执行 `backend/use-mysql57.ps1`，或将 `backend/.env.mysql57` 复制为 `backend/.env`
- 使用 `MySQL 8+` 时，可执行 `backend/use-mysql8.ps1`，或将 `backend/.env.mysql8` 复制为 `backend/.env`
- `DB_MYSQL57_COMPAT=True` 时使用项目内兼容后端，`False` 时使用官方 MySQL 后端
- 如需手动覆盖数据库引擎，可在 `.env` 中设置 `DB_ENGINE`
- 切换脚本会在覆盖前自动备份当前 `backend/.env`
- 切换完成后请重新启动后端服务
- 若后续统一升级到更高版本 `Django`，仍需重新验证依赖兼容性

## 8. Linux 一键部署

适用于新 Linux 机器的快速落地部署，入口脚本为 [deploy/linux_oneclick.sh](C:/Users/华硕/PycharmProjects/ai_plat/deploy/linux_oneclick.sh)。

脚本会自动完成以下动作：

- 识别 `apt` / `dnf` / `yum` 系系统，并按需重写系统源到阿里云镜像
- 安装 `git`、`nginx`、`mysql/mariadb`、`python3`、`nodejs`
- 生成 `backend/.env` 和 `frontend/.env.production.local`
- 初始化数据库、安装 Python / Node.js 依赖、执行 `migrate`
- 构建前端静态资源，并注册 `systemd + gunicorn + nginx`

最小示例：

```bash
chmod +x deploy/linux_oneclick.sh
sudo DOMAIN=test.example.com SERVER_IP=192.168.1.10 DB_PASSWORD=ChangeMe_123456 DEFAULT_ADMIN_PASSWORD=ChangeMe_123456 bash deploy/linux_oneclick.sh
```

常用环境变量：

- `DOMAIN` / `SERVER_IP`：用于生成站点访问地址、`ALLOWED_HOSTS` 与 CORS
- `DB_NAME`、`DB_USER`、`DB_PASSWORD`：数据库初始化参数
- `DJANGO_SECRET_KEY`、`DJANGO_DEBUG`、`DEFAULT_ADMIN_*`：Django 与初始管理员配置
- `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`：AI 生成能力配置
- `OFFLINE_MODE=true`：启用离线部署模式，从 `deploy/offline` 读取本地包
- `OFFLINE_DIR`：自定义离线包根目录
- `ENABLE_MIRROR_REWRITE=false`：关闭阿里云镜像源改写

部署完成后，前端通过 Nginx 暴露，后端健康检查地址默认为 `http://127.0.0.1:8000/api/health`。

### 离线部署方式

适用于目标机无法访问公网，但你可以提前手动下载依赖包并拷到项目目录的场景。

推荐流程是“目标机先探测，有网机再准备”：

```bash
# 第 1 步：在目标机执行，生成画像文件
chmod +x deploy/probe_target_env.sh
bash deploy/probe_target_env.sh

# 第 2 步：把 deploy/offline/target-profile.env 带到有网机器后执行
chmod +x deploy/prepare_offline_bundle.sh
sudo bash deploy/prepare_offline_bundle.sh
```

说明：

- [deploy/probe_target_env.sh](C:/Users/华硕/PycharmProjects/ai_plat/deploy/probe_target_env.sh) 会自动识别目标机的系统、包管理器、架构，以及是否已安装 `nginx`、数据库客户端、`Python 3.8+`
- [deploy/prepare_offline_bundle.sh](C:/Users/华硕/PycharmProjects/ai_plat/deploy/prepare_offline_bundle.sh) 会读取 `deploy/offline/target-profile.env`，自动决定默认要下载哪些离线资源
- 如果有网准备机和目标机不是同一包管理器家族，例如准备机是 `apt` 而目标机是 `yum`，脚本会阻止自动下载 OS 包；这时应在同类系统上准备，或用 `SKIP_OS_PACKAGES=true` 只准备 wheel 和前端产物

离线目录约定如下：

```text
deploy/offline/
├─ os-packages/        # 可选，系统包：apt 用 .deb，yum/dnf 用 .rpm
├─ python/             # 必需，后端依赖 wheel 文件
├─ frontend-dist/      # 可选，前端 dist 目录
└─ frontend-dist.tar.gz # 推荐，前端构建产物压缩包
```

离线模式最少需要准备：

- `deploy/offline/python/`：包含后端依赖的 `.whl` 文件，至少覆盖 `backend/requirements.txt` 中所有包
- `deploy/offline/frontend-dist.tar.gz` 或 `deploy/offline/frontend-dist/index.html`：前端构建产物

如果目标机连 `python3`、`nginx`、`mysql/mariadb` 都没有，再额外准备：

- `deploy/offline/os-packages/`：对应系统的本地安装包集合

推荐在有网机器上准备前端构建产物：

```bash
cd frontend
npm install
npm run build
tar -czf ../deploy/offline/frontend-dist.tar.gz -C dist .
```

推荐在有网机器上准备 Python wheel：

```bash
python -m pip download -r backend/requirements.txt -d deploy/offline/python
python -m pip download gunicorn -d deploy/offline/python
```

也可以直接在一台有网、且尽量与目标机同系统的大版本 Linux 上执行：

```bash
chmod +x deploy/prepare_offline_bundle.sh
sudo bash deploy/prepare_offline_bundle.sh
```

该脚本会自动完成：

- 下载 `deploy/offline/python/` 下的后端 wheel
- 构建并打包 `deploy/offline/frontend-dist.tar.gz`
- 下载 `deploy/offline/os-packages/` 下的系统包

说明：

- `apt` / `dnf` 环境会默认尝试下载 Python 运行时包
- `yum` 环境会根据目标画像自动判断是否需要 `nginx` / `mariadb`，但如果目标缺少 `python3.8+`，通常仍需要你在 `deploy/offline/target-profile.env` 里补 `TARGET_PYTHON_PACKAGE_HINTS`
- 例如 `CentOS 7` 可尝试：`TARGET_PYTHON_PACKAGE_HINTS="python38 python38-pip python38-setuptools"`

离线部署命令：

```bash
chmod +x deploy/linux_oneclick.sh
sudo OFFLINE_MODE=true DOMAIN=test.example.com SERVER_IP=192.168.1.10 DB_PASSWORD=ChangeMe_123456 DEFAULT_ADMIN_PASSWORD=ChangeMe_123456 bash deploy/linux_oneclick.sh
```

离线模式下脚本行为如下：

- 跳过镜像源改写、pip 镜像配置、npm registry 配置
- 若 `deploy/offline/os-packages/` 下存在本地系统包，则优先从本地安装
- 后端通过 `pip install --no-index --find-links=...` 安装 wheel
- 前端不再执行 `npm build`，而是直接解压 `frontend-dist.tar.gz`

常见故障排查：

- 如果出现 `curl: (6) Could not resolve host: mirrors.aliyun.com`，这不是脚本逻辑失败，而是目标机器当前 DNS 不可用
- 先检查 `/etc/resolv.conf` 是否存在可用 `nameserver`
- 可临时写入：

```bash
cat >/etc/resolv.conf <<'EOF'
nameserver 223.5.5.5
nameserver 223.6.6.6
EOF
getent hosts mirrors.aliyun.com
```

- 确认能解析后再重新执行一键部署
- `ENABLE_MIRROR_REWRITE=false` 只能关闭镜像源改写，本身不能修复 DNS 故障
- 如果离线模式报 `Offline mode requires Python wheels`，说明 [deploy/offline/python](C:/Users/华硕/PycharmProjects/ai_plat/deploy/offline/python) 下缺少 `.whl`
- 如果离线模式报 `Frontend dist archive must contain index.html`，说明前端压缩包目录层级不对，需保证根目录或 `dist/` 目录下直接有 `index.html`

## 9. Docker 微服务部署

当前仓库提供 [docker-compose.microservices.yml](C:/Users/华硕/PycharmProjects/ai_plat/docker-compose.microservices.yml) 作为标准容器化部署入口，包含：

- `db`：`MySQL 8`，自动执行 [sql/init_mysql.sql](C:/Users/华硕/PycharmProjects/ai_plat/sql/init_mysql.sql)
- `backend`：基于 [backend/Dockerfile](C:/Users/华硕/PycharmProjects/ai_plat/backend/Dockerfile) 构建，启动时执行 [backend/docker/entrypoint.sh](C:/Users/华硕/PycharmProjects/ai_plat/backend/docker/entrypoint.sh)
- `frontend`：基于 [frontend/Dockerfile](C:/Users/华硕/PycharmProjects/ai_plat/frontend/Dockerfile) 构建静态站点
- `nginx`：加载 [deploy/nginx/gateway.conf](C:/Users/华硕/PycharmProjects/ai_plat/deploy/nginx/gateway.conf)，统一转发 `/`、`/api/` 与 `/static/`

启动步骤：

```bash
cp deploy/docker/.env.example .env
docker compose --env-file .env -f docker-compose.microservices.yml up -d --build
```

建议至少修改以下变量：

- `DJANGO_SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `DB_PASSWORD`
- `DEFAULT_ADMIN_PASSWORD`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `AI_API_KEY`

常用运维命令：

```bash
docker compose -f docker-compose.microservices.yml ps
docker compose -f docker-compose.microservices.yml logs -f backend
docker compose -f docker-compose.microservices.yml logs -f nginx
docker compose -f docker-compose.microservices.yml down
```

容器部署模式下，后端会自动等待数据库、执行迁移，并在 `DJANGO_COLLECTSTATIC=1` 时将静态文件收集到 `STATIC_ROOT=/app/staticfiles`，再由网关容器统一暴露。

## 10. Docker 单镜像部署

如果你希望最终只交付一个应用镜像，而不是前后端多个业务容器，可以使用以下文件：

- [Dockerfile.single](C:/Users/华硕/PycharmProjects/ai_plat/Dockerfile.single)
- [docker-compose.single-image.yml](C:/Users/华硕/PycharmProjects/ai_plat/docker-compose.single-image.yml)
- [deploy/single-image/nginx.conf](C:/Users/华硕/PycharmProjects/ai_plat/deploy/single-image/nginx.conf)
- [deploy/single-image/entrypoint.sh](C:/Users/华硕/PycharmProjects/ai_plat/deploy/single-image/entrypoint.sh)

该模式的结构是：

- `app`：单个应用镜像，内部运行 `nginx + gunicorn`
- `db`：可选的独立 `MySQL 8` 容器；也可以替换成外部 MySQL

启动示例：

```bash
cp deploy/single-image/.env.example .env
docker compose --env-file .env -f docker-compose.single-image.yml up -d --build
```

镜像构建和运行逻辑：

- 构建阶段使用 `Node.js` 打包前端静态资源
- 运行阶段使用 `Python 3.11 + Nginx`
- 容器启动时自动等待数据库、执行 `migrate`、执行 `collectstatic`
- `nginx` 直接服务前端页面，并将 `/api/` 代理到容器内的 `gunicorn`
- `/static/` 由同一容器内的 `nginx` 直接映射 Django 收集后的静态文件

如需接外部 MySQL：

- 删除或忽略 `db` 服务
- 把 `DB_HOST` 改成外部数据库地址
- 保持 `DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME` 与目标库一致
- 如果数据库在容器外部，首次启动前请确认防火墙和白名单已放通

单镜像模式更适合：

- 需要把业务应用交付为一个镜像
- 前端、后端和网关希望统一版本发布
- 数据库可以独立托管在外部或单独容器中

## 11. 推荐使用流程

1. 进入“项目管理”，先创建项目
2. 为项目创建“环境”，配置环境地址、默认 Header、环境变量
3. 在“接口管理”中创建模块并维护接口资产
4. 对单接口进行“预检”或“快速执行”，确认请求配置正确
5. 在“自动化测试”中编排场景步骤，配置变量提取、前置条件、业务断言
6. 如需参数化回归，为场景绑定数据集并设置执行模式
7. 在“场景报告”与“执行历史”中查看步骤明细、上下文快照和错误原因
8. 需要批量建模时，使用“AI 助手”通过业务描述或 OpenAPI 文档生成草稿并导入
9. 如需多人协作，使用“权限与审计”页面管理成员与项目授权
10. 如需查看机器 / 服务指标，在“监控配置”和“资源监控”中接入监控平台

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

### 3. 环境 / 全局变量表达式

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
- `POST /api/monitor/platforms/runtime-check`
- `POST /api/monitor/platforms/{id}/deploy`
- `POST /api/monitor/platforms/{id}/upload-package`
- `GET /api/monitor/platforms/{id}/status`
- `GET /api/monitor/platforms/{id}/logs`
- `GET /api/monitor/platforms/{id}/targets`
- `GET /api/monitor/platforms/{id}/metrics/latest`
- `GET /api/monitor/platforms/{id}/metrics/history`

## 监控功能说明

监控管理操作仅允许管理员执行。典型流程如下：

1. 在“监控配置”中新建监控平台，填写主机、SSH 账号密码、部署方式
2. 保存前可先执行 Docker 环境检测，确认目标机是否已安装 Docker / Compose，以及当前 SSH 账号是否可访问 Docker Engine
3. 选择在线部署，或上传离线包后部署
4. 根据平台类型配置单机或多个目标主机；若目标机已有监控组件，系统会优先复用现有栈并刷新采集配置
5. 在线部署时若缺少 Docker / Compose，系统会尝试自动安装；遇到常见证书或软件源问题时会尝试自动纠错
6. 部署成功后，在“资源监控”页面查看最新指标和历史趋势

## 适用场景

- 接口测试平台原型验证
- 团队内部接口回归与日常巡检
- 多项目、多环境的接口资产沉淀
- 基于数据集的批量自动化回归
- 结合 AI 辅助生成测试草稿与 OpenAPI 快速导入
- 结合主机监控的测试平台一体化管理
