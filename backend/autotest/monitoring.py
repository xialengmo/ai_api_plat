from __future__ import annotations

import os
import posixpath
import re
import time
from typing import Tuple

from django.utils import timezone

from autotest.models import MonitorPlatform

try:
    import paramiko
except Exception:  # noqa: BLE001
    paramiko = None


def _append_log(platform: MonitorPlatform, message: str, level: str = "info") -> None:
    logs = platform.deploy_logs if isinstance(platform.deploy_logs, list) else []
    logs.append(
        {
            "time": timezone.now().isoformat(),
            "level": str(level or "info"),
            "message": str(message or ""),
        }
    )
    if len(logs) > 200:
        logs = logs[-200:]
    platform.deploy_logs = logs


def _require_paramiko() -> None:
    if paramiko is None:
        raise RuntimeError("缺少依赖 paramiko，请先安装后再执行远程部署")


def _ssh_connect(platform: MonitorPlatform):
    _require_paramiko()
    if not platform.ssh_password:
        raise RuntimeError("未配置 SSH 密码，无法自动部署")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=str(platform.host or "").strip(),
        port=int(platform.ssh_port or 22),
        username=str(platform.ssh_username or "").strip(),
        password=str(platform.ssh_password or ""),
        timeout=15,
    )
    return client


def _run_remote(client, command: str, timeout: int = 180) -> Tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = int(stdout.channel.recv_exit_status())
    return code, out, err


def _quote_single(text: str) -> str:
    return "'" + str(text or "").replace("'", "'\"'\"'") + "'"


def _run_as_root(client, platform: MonitorPlatform, command: str, timeout: int = 300) -> Tuple[int, str, str]:
    code, out, err = _run_remote(client, command, timeout=timeout)
    if code == 0:
        return code, out, err

    wrapped = f"sudo -n bash -lc {_quote_single(command)}"
    code2, out2, err2 = _run_remote(client, wrapped, timeout=timeout)
    if code2 == 0:
        return code2, out2, err2

    if platform.ssh_password:
        pw = _quote_single(platform.ssh_password)
        wrapped_pw = f"echo {pw} | sudo -S -p '' bash -lc {_quote_single(command)}"
        code3, out3, err3 = _run_remote(client, wrapped_pw, timeout=timeout)
        return code3, out3, err3
    return code2, out2, err2


def _is_client_active(client) -> bool:
    try:
        transport = client.get_transport()
        return bool(transport and transport.is_active())
    except Exception:
        return False


def _reconnect_client_if_needed(client, platform: MonitorPlatform, stage: str = ""):
    if _is_client_active(client):
        return client
    try:
        client.close()
    except Exception:
        pass
    _append_log(platform, f"SSH 会话在{stage or '部署阶段'}已断开，正在自动重连")
    platform.save(update_fields=["deploy_logs", "updated_at"])
    return _ssh_connect(platform)


def _extract_repo_id(error_text: str) -> str:
    text = str(error_text or "")
    match = re.search(r"(?:repo|repository)\s+'([^']+)'", text, flags=re.IGNORECASE)
    return str(match.group(1)).strip() if match else ""


def _ai_plan_repair_actions(error_text: str) -> list[dict]:
    # 关键逻辑说明(lxl): AI 只返回白名单动作，不直接执行任意 shell。
    api_key = str(os.getenv("AI_API_KEY", "")).strip()
    if not api_key:
        return []
    try:
        import json
        from autotest.ai_generator import _invoke_model_text

        base_url = str(os.getenv("AI_BASE_URL", "https://api.openai.com/v1")).strip().rstrip("/")
        model = str(os.getenv("AI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
        timeout = int(os.getenv("AI_TIMEOUT_SECONDS", "45"))
        system_prompt = (
            "你是 Linux 运维故障修复助手。"
            "仅输出 JSON。"
            "格式:{\"actions\":[{\"type\":\"sync_time\"},{\"type\":\"disable_repo\",\"repo\":\"xxx\"},{\"type\":\"relax_ssl_install\"}]}。"
            "type 仅允许 sync_time/disable_repo/relax_ssl_install。"
        )
        user_prompt = f"docker/compose 安装失败，错误日志如下:\n{error_text}\n请返回最小修复动作。"
        content, _, _ = _invoke_model_text(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        data = json.loads(content or "{}")
        actions = data.get("actions") if isinstance(data, dict) else []
        if not isinstance(actions, list):
            return []
        normalized = []
        for item in actions:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type") or "").strip().lower()
            if t not in {"sync_time", "disable_repo", "relax_ssl_install"}:
                continue
            row = {"type": t}
            if t == "disable_repo":
                row["repo"] = str(item.get("repo") or "").strip()
            normalized.append(row)
        return normalized[:5]
    except Exception:
        return []


def _execute_repair_actions(client, platform: MonitorPlatform, actions: list[dict]) -> None:
    for action in actions or []:
        t = str(action.get("type") or "").strip().lower()
        if t == "sync_time":
            _append_log(platform, "自动纠错: 尝试同步系统时间")
            controller_now = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd = r"""
if command -v timedatectl >/dev/null 2>&1; then timedatectl set-ntp true || true; fi
if command -v chronyc >/dev/null 2>&1; then chronyc -a makestep || true; fi
if command -v ntpdate >/dev/null 2>&1; then ntpdate -u ntp.aliyun.com || ntpdate -u pool.ntp.org || true; fi
date || true
"""
            # 关键逻辑说明(lxl): 当 NTP 不可用时，直接将目标机时间校准到平台控制端时间，修复证书“not yet valid”。
            cmd += f"\nif command -v date >/dev/null 2>&1; then date -s '{controller_now}' || true; fi\n"
            cmd += "\nif command -v hwclock >/dev/null 2>&1; then hwclock -w || true; fi\n"
            _run_as_root(client, platform, cmd, timeout=90)
            continue

        if t == "disable_repo":
            repo = str(action.get("repo") or "").strip()
            if not repo:
                continue
            _append_log(platform, f"自动纠错: 尝试禁用异常仓库 {repo}")
            cmd = (
                f"if command -v dnf >/dev/null 2>&1; then dnf config-manager --set-disabled {repo} || true; fi;"
                f"if command -v yum-config-manager >/dev/null 2>&1; then yum-config-manager --disable {repo} || true; fi;"
                f"if [ -d /etc/yum.repos.d ]; then "
                f"sed -i -r '/^\\[{repo}\\]/,/^\\[/{'{'}s/^[[:space:]]*enabled[[:space:]]*=.*/enabled=0/{'}'}/g' /etc/yum.repos.d/*.repo 2>/dev/null || true; "
                f"fi;"
            )
            _run_as_root(client, platform, cmd, timeout=60)
            continue

        if t == "relax_ssl_install":
            _append_log(platform, "自动纠错: 尝试使用宽松 SSL 参数安装 docker/compose")
            repo = str(action.get("repo") or "").strip()
            safe_repo = repo if re.match(r"^[A-Za-z0-9._-]+$", repo) else ""
            disable_opt = (
                f"--disablerepo={safe_repo} --setopt={safe_repo}.sslverify=false --setopt={safe_repo}.gpgcheck=0"
                if safe_repo
                else ""
            )
            cmd = r"""
set -e
if command -v dnf >/dev/null 2>&1; then
  dnf install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker || true
  dnf install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker-compose-plugin || dnf install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker-compose || true
elif command -v yum >/dev/null 2>&1; then
  yum install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker || true
  yum install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker-compose-plugin || yum install -y --setopt=sslverify=false --nogpgcheck DISABLE_OPT docker-compose || true
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update -y || true
  apt-get install -y docker.io || true
  apt-get install -y docker-compose-plugin || apt-get install -y docker-compose || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable docker >/dev/null 2>&1 || true
  systemctl restart docker >/dev/null 2>&1 || systemctl start docker >/dev/null 2>&1 || true
else
  service docker restart >/dev/null 2>&1 || service docker start >/dev/null 2>&1 || true
fi
"""
            cmd = cmd.replace("DISABLE_OPT", disable_opt).replace("  ", " ").replace("\n\n", "\n")
            _run_as_root(client, platform, cmd, timeout=240)


def _attempt_self_heal_for_docker_install(client, platform: MonitorPlatform, error_text: str) -> None:
    text = str(error_text or "")
    lower = text.lower()
    actions = []

    if "certificate is not yet valid" in lower or "curl error (60)" in lower or "ssl certificate problem" in lower:
        actions.append({"type": "sync_time"})
        repo = _extract_repo_id(text)
        if repo:
            actions.append({"type": "disable_repo", "repo": repo})
            actions.append({"type": "relax_ssl_install", "repo": repo})
        else:
            actions.append({"type": "relax_ssl_install"})

    ai_actions = _ai_plan_repair_actions(text)
    for item in ai_actions:
        if item not in actions:
            actions.append(item)

    if not actions:
        return
    _append_log(platform, f"检测到安装异常，开始自动纠错（动作数: {len(actions)}）")
    platform.save(update_fields=["deploy_logs", "updated_at"])
    client = _reconnect_client_if_needed(client, platform, stage="自动纠错前")
    _execute_repair_actions(client, platform, actions)


def _ensure_docker_compose(client, platform: MonitorPlatform) -> None:
    check_cmd = "docker --version >/dev/null 2>&1 && (docker compose version >/dev/null 2>&1 || docker-compose --version >/dev/null 2>&1)"
    code, _, _ = _run_remote(client, check_cmd, timeout=20)
    if code == 0:
        return

    _append_log(platform, "检测到 docker/compose 缺失，开始自动安装")
    platform.save(update_fields=["deploy_logs", "updated_at"])

    install_script = r"""
set -e
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io || true
  apt-get install -y docker-compose-plugin || apt-get install -y docker-compose || true
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y docker || true
  dnf install -y docker-compose-plugin || dnf install -y docker-compose || true
elif command -v yum >/dev/null 2>&1; then
  yum install -y docker || true
  yum install -y docker-compose-plugin || yum install -y docker-compose || true
else
  echo "Unsupported package manager (need apt-get/dnf/yum)" >&2
  exit 2
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable docker >/dev/null 2>&1 || true
  systemctl restart docker >/dev/null 2>&1 || systemctl start docker >/dev/null 2>&1 || true
else
  service docker restart >/dev/null 2>&1 || service docker start >/dev/null 2>&1 || true
fi

if docker compose version >/dev/null 2>&1 || docker-compose --version >/dev/null 2>&1; then
  exit 0
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
elif command -v wget >/dev/null 2>&1; then
  wget -q -O /usr/local/bin/docker-compose "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-$(uname -s)-$(uname -m)"
else
  echo "curl/wget not found, cannot install docker-compose standalone" >&2
  exit 3
fi
chmod +x /usr/local/bin/docker-compose
"""
    code, out, err = _run_as_root(client, platform, install_script, timeout=420)
    if code != 0:
        err_text = (err or out or "").strip()
        _append_log(platform, f"docker/compose 安装失败，进入自动纠错: {err_text[:220]}", level="error")
        platform.save(update_fields=["deploy_logs", "updated_at"])
        _attempt_self_heal_for_docker_install(client, platform, err_text)

    client = _reconnect_client_if_needed(client, platform, stage="自动纠错后校验前")
    code2, _, err2 = _run_remote(client, check_cmd, timeout=20)
    if code2 != 0:
        raise RuntimeError(f"自动安装 docker/compose 失败: {(err2 or err or out).strip()}")


def _run_compose_up(client, platform: MonitorPlatform, workdir: str, timeout: int = 300) -> None:
    detect_cmd = (
        "if docker compose version >/dev/null 2>&1; then echo 'docker compose'; "
        "elif docker-compose --version >/dev/null 2>&1; then echo 'docker-compose'; "
        "else echo ''; fi"
    )
    code0, out0, err0 = _run_remote(client, detect_cmd, timeout=30)
    compose_cmd = str(out0 or "").strip()
    if code0 != 0 or not compose_cmd:
        code0, out0, err0 = _run_as_root(client, platform, detect_cmd, timeout=30)
        compose_cmd = str(out0 or "").strip()
    if not compose_cmd:
        raise RuntimeError((err0 or out0).strip() or "未检测到可用的 docker compose 命令")

    cmd = f"cd {workdir} && {compose_cmd} up -d"
    code, out, err = _run_remote(client, cmd, timeout=timeout)
    if code == 0:
        return
    code2, out2, err2 = _run_as_root(client, platform, cmd, timeout=timeout)
    if code2 != 0:
        raise RuntimeError((err2 or out2 or err or out).strip() or "启动 docker compose 失败")


def _collect_monitor_scrape_targets(platform: MonitorPlatform, include_fallback: bool = True) -> list[dict]:
    rows = list(platform.monitor_targets.filter(enabled=True).order_by("sort_order", "id"))
    targets = []
    host_seen = set()
    for row in rows:
        host = str(getattr(row, "host", "") or "").strip()
        if not host or host in host_seen:
            continue
        host_seen.add(host)
        targets.append(
            {
                "host": host,
                "node_exporter_port": int(getattr(row, "node_exporter_port", 9100) or 9100),
                "cadvisor_port": int(getattr(row, "cadvisor_port", 8080) or 8080),
            }
        )
    if not targets and include_fallback:
        host = str(platform.host or "").strip()
        if host:
            targets.append({"host": host, "node_exporter_port": 9100, "cadvisor_port": 8080})
    return targets


def _render_prometheus_config(platform: MonitorPlatform) -> str:
    platform_type = str(platform.platform_type or "").strip().lower()
    include_local_exporters = platform_type != MonitorPlatform.PLATFORM_TYPE_HOST_CLUSTER
    scrape_targets = _collect_monitor_scrape_targets(platform, include_fallback=not include_local_exporters)
    node_targets = ['"node-exporter:9100"'] if include_local_exporters else []
    cadvisor_targets = ['"cadvisor:8080"'] if include_local_exporters else []
    node_targets.extend([f'"{item["host"]}:{int(item["node_exporter_port"])}"' for item in scrape_targets])
    cadvisor_targets.extend([f'"{item["host"]}:{int(item["cadvisor_port"])}"' for item in scrape_targets])
    return f"""global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["prometheus:9090"]
  - job_name: "node-exporter"
    static_configs:
      - targets: [{", ".join(node_targets)}]
  - job_name: "cadvisor"
    static_configs:
      - targets: [{", ".join(cadvisor_targets)}]
"""


def _render_compose_file(include_local_exporters: bool = True) -> str:
    exporter_block = """
  node-exporter:
    image: prom/node-exporter:v1.8.1
    container_name: node-exporter
    restart: always
    command:
      - "--path.rootfs=/host"
    volumes:
      - "/:/host:ro,rslave"

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    container_name: cadvisor
    restart: always
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:rw
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
""" if include_local_exporters else ""
    return f"""version: "3.3"

services:
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: prometheus
    restart: always
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: alertmanager
    restart: always
    ports:
      - "9093:9093"
{exporter_block}

volumes:
  prometheus_data:
"""


def _deploy_online(platform: MonitorPlatform) -> None:
    remote_dir = "/opt/ai-monitor-stack"
    include_local_exporters = str(platform.platform_type or "").strip().lower() != MonitorPlatform.PLATFORM_TYPE_HOST_CLUSTER
    compose_file = _render_compose_file(include_local_exporters=include_local_exporters)
    prom_file = _render_prometheus_config(platform)
    client = _ssh_connect(platform)
    try:
        _ensure_docker_compose(client, platform)
        client = _reconnect_client_if_needed(client, platform, stage="环境检查后")
        _append_log(platform, "远程环境检查通过，开始写入 Prometheus 部署文件")
        platform.save(update_fields=["deploy_logs", "updated_at"])

        client = _reconnect_client_if_needed(client, platform, stage="写入部署文件前")
        sftp = client.open_sftp()
        try:
            try:
                sftp.stat(remote_dir)
            except Exception:
                _run_as_root(client, platform, f"mkdir -p {remote_dir}", timeout=60)
            with sftp.open(posixpath.join(remote_dir, "docker-compose.yml"), "w") as f:
                f.write(compose_file)
            with sftp.open(posixpath.join(remote_dir, "prometheus.yml"), "w") as f:
                f.write(prom_file)
        finally:
            sftp.close()

        client = _reconnect_client_if_needed(client, platform, stage="启动服务前")
        _run_compose_up(client, platform, remote_dir, timeout=360)
    finally:
        client.close()


def _deploy_offline(platform: MonitorPlatform) -> None:
    package_path = str(platform.offline_package_path or "").strip()
    if not package_path or not os.path.exists(package_path):
        raise RuntimeError("离线部署模式下未上传有效离线包")

    remote_dir = "/opt/ai-monitor-stack"
    remote_pkg = f"/tmp/ai-monitor-offline-{platform.id}-{int(time.time())}.tar.gz"
    client = _ssh_connect(platform)
    try:
        _ensure_docker_compose(client, platform)
        client = _reconnect_client_if_needed(client, platform, stage="环境检查后")
        _append_log(platform, "开始上传离线包到目标机器")
        platform.save(update_fields=["deploy_logs", "updated_at"])

        client = _reconnect_client_if_needed(client, platform, stage="离线包上传前")
        sftp = client.open_sftp()
        try:
            sftp.put(package_path, remote_pkg)
        finally:
            sftp.close()

        client = _reconnect_client_if_needed(client, platform, stage="离线部署执行前")
        shell = (
            f"set -e;"
            f"mkdir -p {remote_dir}/offline;"
            f"rm -rf {remote_dir}/offline/*;"
            f"tar -xzf {remote_pkg} -C {remote_dir}/offline;"
            f"if [ -d {remote_dir}/offline/images ]; then "
            f"for f in {remote_dir}/offline/images/*.tar; do [ -f \"$f\" ] && docker load -i \"$f\"; done; "
            f"fi;"
            f"if [ -f {remote_dir}/offline/install.sh ]; then "
            f"bash {remote_dir}/offline/install.sh; "
            f"elif [ -f {remote_dir}/offline/docker-compose.yml ]; then "
            f"if docker compose version >/dev/null 2>&1; then COMPOSE='docker compose'; "
            f"elif docker-compose --version >/dev/null 2>&1; then COMPOSE='docker-compose'; "
            f"else echo '未检测到 docker compose 命令' >&2; exit 3; fi; "
            f"cd {remote_dir}/offline && $COMPOSE up -d; "
            f"elif [ -f {remote_dir}/offline/compose/docker-compose.yml ]; then "
            f"if docker compose version >/dev/null 2>&1; then COMPOSE='docker compose'; "
            f"elif docker-compose --version >/dev/null 2>&1; then COMPOSE='docker-compose'; "
            f"else echo '未检测到 docker compose 命令' >&2; exit 3; fi; "
            f"cd {remote_dir}/offline/compose && $COMPOSE up -d; "
            f"else echo '离线包中缺少 install.sh 或 docker-compose.yml' >&2; exit 2; fi;"
            f"rm -f {remote_pkg};"
        )
        code, out, err = _run_as_root(client, platform, shell, timeout=480)
        if code != 0:
            raise RuntimeError(err.strip() or out.strip() or "离线部署失败")
    finally:
        client.close()


def deploy_monitor_platform(platform: MonitorPlatform, trigger: str = "manual") -> MonitorPlatform:
    platform.status = MonitorPlatform.STATUS_DEPLOYING
    platform.last_error = ""
    _append_log(platform, f"开始部署（触发方式: {trigger}，模式: {platform.deploy_mode}）")
    platform.save(update_fields=["status", "last_error", "deploy_logs", "updated_at"])

    try:
        mode = str(platform.deploy_mode or MonitorPlatform.DEPLOY_MODE_ONLINE).strip().lower()
        if mode == MonitorPlatform.DEPLOY_MODE_OFFLINE:
            _deploy_offline(platform)
        else:
            _deploy_online(platform)

        host = str(platform.host or "").strip()
        platform.prometheus_url = f"http://{host}:9090"
        platform.grafana_url = None
        platform.alertmanager_url = f"http://{host}:9093"
        platform.status = MonitorPlatform.STATUS_RUNNING
        platform.last_error = ""
        platform.last_deployed_at = timezone.now()
        _append_log(platform, "部署成功，服务已启动")
    except Exception as exc:  # noqa: BLE001
        platform.status = MonitorPlatform.STATUS_FAILED
        platform.last_error = str(exc)[:500]
        _append_log(platform, f"部署失败: {exc}", level="error")
    finally:
        platform.save(
            update_fields=[
                "status",
                "last_error",
                "deploy_logs",
                "last_deployed_at",
                "prometheus_url",
                "grafana_url",
                "alertmanager_url",
                "updated_at",
            ]
        )
    return platform
