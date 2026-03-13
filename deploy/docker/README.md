# Docker 微服务部署

该部署方式会把项目拆成 4 个容器：

- `frontend`：前端静态资源容器，由 Nginx 提供页面访问
- `backend`：`Django + Gunicorn` API 容器
- `nginx`：统一网关容器，负责转发 `/`、`/api/` 和 `/static/`
- `db`：`MySQL 8` 容器

## 1. 准备环境变量

```bash
cp deploy/docker/.env.example .env
```

建议至少修改以下配置：

- `DJANGO_SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `DB_PASSWORD`
- `DEFAULT_ADMIN_PASSWORD`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `AI_API_KEY`

如果用户通过 `http://your-domain` 访问，典型配置如下：

- `DJANGO_ALLOWED_HOSTS=your-domain,localhost,127.0.0.1`
- `DJANGO_CORS_ALLOWED_ORIGINS=http://your-domain`

## 2. 启动整套服务

```bash
docker compose --env-file .env -f docker-compose.microservices.yml up -d --build
```

## 3. 查看运行状态

```bash
docker compose -f docker-compose.microservices.yml ps
docker compose -f docker-compose.microservices.yml logs -f backend
docker compose -f docker-compose.microservices.yml logs -f nginx
```

## 4. 访问地址

- 前端入口：`http://server-ip/`
- 后端健康检查：`http://server-ip/api/health`

## 5. 停止服务

```bash
docker compose -f docker-compose.microservices.yml down
```

如果连数据卷一起删除：

```bash
docker compose -f docker-compose.microservices.yml down -v
```

## 6. 架构说明

- 浏览器只访问 `nginx` 网关容器
- `nginx` 会将 `/api/` 转发到 `backend:8000`
- `nginx` 会将 `/static/` 映射到后端共享出来的静态文件卷
- `nginx` 会将 `/` 转发到 `frontend:80`
- `backend` 通过 Docker 网络访问 `db:3306`
- 前端构建时固定使用 `VITE_API_BASE_URL=/api`
- 后端容器启动时会等待 MySQL，执行 `migrate`，并在需要时执行 `collectstatic` 后再启动 Gunicorn

## 7. 生产环境建议

- 将 `FRONTEND_PORT` 设为 `80`，或在宿主机 / 负载均衡层反向代理到 `443`
- 在网关容器前补充 TLS 证书
- 如果使用外部 MySQL，可以移除 `db` 服务，并把 `DB_HOST` 指向实际数据库地址
- 如果需要持久化上传文件或离线包，请保留 `backend_storage` 数据卷

