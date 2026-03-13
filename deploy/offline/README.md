# Offline Deployment Assets

Place manually prepared offline assets here before running:

```bash
sudo OFFLINE_MODE=true bash deploy/linux_oneclick.sh
```

Layout:

```text
deploy/offline/
|-- os-packages/         optional system packages (.deb or .rpm)
|-- python/              required Python wheels for backend dependencies
|-- frontend-dist/       optional extracted frontend build output
`-- frontend-dist.tar.gz recommended frontend build archive
```

Minimum required assets:

- `python/*.whl`
- `frontend-dist.tar.gz` or `frontend-dist/index.html`
- `target-profile.env` is recommended; generate it on the target machine with `bash deploy/probe_target_env.sh`

If the target machine does not already have `python3`, `nginx`, or `mysql/mariadb`,
also put the corresponding local OS packages into `os-packages/`.
