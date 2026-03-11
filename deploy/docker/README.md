# Docker Microservice Deployment

This deployment mode splits the project into 4 containers:

- `frontend`: Vite build output served by Nginx
- `backend`: Django + Gunicorn API container
- `nginx`: gateway container for `/`, `/api/`, and `/static/`
- `db`: MySQL 8 container

## 1. Prepare environment variables

```bash
cp deploy/docker/.env.example .env
```

Update at least these values:

- `DJANGO_SECRET_KEY`
- `MYSQL_ROOT_PASSWORD`
- `DB_PASSWORD`
- `DEFAULT_ADMIN_PASSWORD`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `AI_API_KEY`

If users access the site through `http://your-domain`, a typical setup is:

- `DJANGO_ALLOWED_HOSTS=your-domain,localhost,127.0.0.1`
- `DJANGO_CORS_ALLOWED_ORIGINS=http://your-domain`

## 2. Start the stack

```bash
docker compose --env-file .env -f docker-compose.microservices.yml up -d --build
```

## 3. Check status

```bash
docker compose -f docker-compose.microservices.yml ps
docker compose -f docker-compose.microservices.yml logs -f backend
docker compose -f docker-compose.microservices.yml logs -f nginx
```

## 4. Access URLs

- Frontend: `http://server-ip/`
- Backend health check: `http://server-ip/api/health`

## 5. Stop the stack

```bash
docker compose -f docker-compose.microservices.yml down
```

Remove data volumes as well:

```bash
docker compose -f docker-compose.microservices.yml down -v
```

## 6. Architecture notes

- Browsers only talk to the `nginx` gateway container.
- `nginx` proxies `/api/` to `backend:8000`.
- `nginx` serves `/static/` from the shared backend static volume.
- `nginx` proxies `/` to `frontend:80`.
- `backend` connects to `db:3306` over the Docker network.
- The frontend build uses `VITE_API_BASE_URL=/api`.
- The backend container waits for MySQL, runs `migrate`, and can run `collectstatic` before starting Gunicorn.

## 7. Production suggestions

- Set `FRONTEND_PORT=80`, or reverse proxy the gateway to `443`.
- Add TLS certificates in front of the gateway container.
- If you use an external MySQL instance, remove the `db` service and point `DB_HOST` to the real address.
- Keep the `backend_storage` volume if you need persistent uploads or offline packages.
