# 作者: lxl
# 说明: 后台定时采集监控指标，从 Prometheus 拉取数据并持久化到 MonitorMetricSnapshot。
from __future__ import annotations

import logging

import django.db
from django.utils import timezone

from autotest.models import MonitorMetricSnapshot, MonitorPlatform

logger = logging.getLogger("autotest.metrics_collector")


def collect_metrics_for_platform(platform: MonitorPlatform, target_host: str = ""):
    """采集单个平台的监控指标，返回 (metrics_dict, collected_at)。"""
    from autotest.views import (
        _collect_platform_target_hosts,
        _docker_running_count_via_ssh,
        _persist_monitor_metric_snapshot,
        _prometheus_instance_regex,
        _prometheus_query_first,
        _prometheus_query_for_platform,
        _prometheus_query_vector_for_platform,
        _safe_int,
        _safe_number,
        _safe_round,
    )

    prom_url = str(platform.prometheus_url or "").strip()
    if not prom_url:
        raise ValueError(f"平台 {platform.name} 无 Prometheus 地址")

    instance_re = _prometheus_instance_regex(platform, target_host)
    inst_selector = f'{{instance=~"{instance_re}"}}' if instance_re else ""
    inst_filter = f',instance=~"{instance_re}"' if instance_re else ""
    host_instance_re = instance_re

    # ---- PromQL 查询 ----
    cpu_usage = _prometheus_query_for_platform(
        platform,
        f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle"{inst_filter}}}[5m])) * 100)',
    )
    cpu_iowait = _prometheus_query_for_platform(
        platform,
        f'avg(rate(node_cpu_seconds_total{{mode="iowait"{inst_filter}}}[5m])) * 100',
    )
    mem_usage = _prometheus_query_for_platform(
        platform,
        f'(1 - (sum(node_memory_MemAvailable_bytes{inst_selector}) / sum(node_memory_MemTotal_bytes{inst_selector}))) * 100',
    )
    swap_usage = _prometheus_query_for_platform(
        platform,
        f'(1 - (sum(node_memory_SwapFree_bytes{inst_selector}) / sum(node_memory_SwapTotal_bytes{inst_selector}))) * 100',
    )
    disk_usage = _prometheus_query_for_platform(
        platform,
        f'100 * (1 - (sum(node_filesystem_avail_bytes{{fstype!~"tmpfs|overlay"{inst_filter}}}) / sum(node_filesystem_size_bytes{{fstype!~"tmpfs|overlay"{inst_filter}}})))',
    )
    disk_await_ms = _prometheus_query_for_platform(
        platform,
        f'(sum(rate(node_disk_read_time_seconds_total{inst_selector}[5m]) + rate(node_disk_write_time_seconds_total{inst_selector}[5m])) / sum(rate(node_disk_reads_completed_total{inst_selector}[5m]) + rate(node_disk_writes_completed_total{inst_selector}[5m]))) * 1000',
    )
    network_throughput_mbps = _prometheus_query_for_platform(
        platform,
        f'(sum(rate(node_network_receive_bytes_total{{device!~"lo"{inst_filter}}}[5m])) + sum(rate(node_network_transmit_bytes_total{{device!~"lo"{inst_filter}}}[5m]))) * 8 / 1024 / 1024',
    )
    network_drop_rate = _prometheus_query_for_platform(
        platform,
        f'sum(rate(node_network_receive_drop_total{{device!~"lo"{inst_filter}}}[5m]) + rate(node_network_transmit_drop_total{{device!~"lo"{inst_filter}}}[5m]))',
    )
    nic_rx_rows = _prometheus_query_vector_for_platform(
        platform,
        f'sum by (device) (rate(node_network_receive_bytes_total{{device!="lo"{inst_filter}}}[5m])) * 8 / 1024 / 1024',
    )
    nic_tx_rows = _prometheus_query_vector_for_platform(
        platform,
        f'sum by (device) (rate(node_network_transmit_bytes_total{{device!="lo"{inst_filter}}}[5m])) * 8 / 1024 / 1024',
    )
    nic_drop_rows = _prometheus_query_vector_for_platform(
        platform,
        f'sum by (device) (rate(node_network_receive_drop_total{{device!="lo"{inst_filter}}}[5m]) + rate(node_network_transmit_drop_total{{device!="lo"{inst_filter}}}[5m]))',
    )
    nic_map = {}
    for row in nic_rx_rows:
        device = str((row.get("metric") or {}).get("device") or "").strip()
        if not device:
            continue
        nic_map.setdefault(device, {"device": device, "rx_mbps": None, "tx_mbps": None, "drop_rate": None})
        nic_map[device]["rx_mbps"] = _safe_round(row.get("value"), 3)
    for row in nic_tx_rows:
        device = str((row.get("metric") or {}).get("device") or "").strip()
        if not device:
            continue
        nic_map.setdefault(device, {"device": device, "rx_mbps": None, "tx_mbps": None, "drop_rate": None})
        nic_map[device]["tx_mbps"] = _safe_round(row.get("value"), 3)
    for row in nic_drop_rows:
        device = str((row.get("metric") or {}).get("device") or "").strip()
        if not device:
            continue
        nic_map.setdefault(device, {"device": device, "rx_mbps": None, "tx_mbps": None, "drop_rate": None})
        nic_map[device]["drop_rate"] = _safe_round(row.get("value"), 4)
    network_interfaces = []
    for item in nic_map.values():
        rx = _safe_number(item.get("rx_mbps"))
        tx = _safe_number(item.get("tx_mbps"))
        throughput = None
        if rx is not None or tx is not None:
            throughput = _safe_round((rx or 0) + (tx or 0), 3)
        network_interfaces.append(
            {
                "device": item.get("device"),
                "rx_mbps": item.get("rx_mbps"),
                "tx_mbps": item.get("tx_mbps"),
                "throughput_mbps": throughput,
                "drop_rate": item.get("drop_rate"),
            }
        )
    network_interfaces.sort(key=lambda x: _safe_number(x.get("throughput_mbps")) or 0, reverse=True)
    load1 = _prometheus_query_for_platform(
        platform,
        f'avg(node_load1{inst_selector})',
    )
    load5 = _prometheus_query_for_platform(
        platform,
        f'avg(node_load5{inst_selector})',
    )
    host_uptime_hours = _prometheus_query_for_platform(
        platform,
        f'avg((time() - node_boot_time_seconds{inst_selector}) / 3600)',
    )
    cpu_cores = _prometheus_query_for_platform(
        platform,
        f'count(count by (cpu, instance) (node_cpu_seconds_total{{mode="idle"{inst_filter}}}))',
    )
    memory_available_gb = _prometheus_query_for_platform(
        platform,
        f'sum(node_memory_MemAvailable_bytes{inst_selector}) / 1024 / 1024 / 1024',
    )
    disk_free_gb = _prometheus_query_for_platform(
        platform,
        f'sum(node_filesystem_avail_bytes{{fstype!~"tmpfs|overlay"{inst_filter}}}) / 1024 / 1024 / 1024',
    )
    disk_read_mbps = _prometheus_query_for_platform(
        platform,
        f'sum(rate(node_disk_read_bytes_total{inst_selector}[5m])) * 8 / 1024 / 1024',
    )
    disk_write_mbps = _prometheus_query_for_platform(
        platform,
        f'sum(rate(node_disk_written_bytes_total{inst_selector}[5m])) * 8 / 1024 / 1024',
    )
    network_rx_mbps = _prometheus_query_for_platform(
        platform,
        f'sum(rate(node_network_receive_bytes_total{{device!~"lo"{inst_filter}}}[5m])) * 8 / 1024 / 1024',
    )
    network_tx_mbps = _prometheus_query_for_platform(
        platform,
        f'sum(rate(node_network_transmit_bytes_total{{device!~"lo"{inst_filter}}}[5m])) * 8 / 1024 / 1024',
    )
    tcp_established = _prometheus_query_for_platform(
        platform,
        f'sum(node_netstat_Tcp_CurrEstab{inst_selector})',
    )
    tcp_time_wait = _prometheus_query_for_platform(
        platform,
        f'sum(node_sockstat_TCP_tw{inst_selector})',
    )
    process_running = _prometheus_query_for_platform(
        platform,
        f'sum(node_procs_running{inst_selector})',
    )
    process_blocked = _prometheus_query_for_platform(
        platform,
        f'sum(node_procs_blocked{inst_selector})',
    )
    container_restart_count = _prometheus_query_first(
        platform,
        [
            'sum(kube_pod_container_status_restarts_total)',
            'sum(container_restart_count)',
        ],
    )
    pod_abnormal_count = _prometheus_query_first(
        platform,
        [
            'sum(kube_pod_status_phase{phase=~"Pending|Failed|Unknown"})',
            'sum(kube_pod_container_status_waiting_reason)',
        ],
    )
    api_qps = _prometheus_query_first(
        platform,
        [
            'sum(rate(http_requests_total[5m]))',
            'sum(rate(http_server_requests_seconds_count[5m]))',
        ],
    )
    api_p95_ms = _prometheus_query_first(
        platform,
        [
            'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000',
            'histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le)) * 1000',
        ],
    )
    api_5xx_rate = _prometheus_query_first(
        platform,
        [
            '100 * (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))',
            '100 * (sum(rate(http_server_requests_seconds_count{status=~"5.."}[5m])) / sum(rate(http_server_requests_seconds_count[5m])))',
        ],
    )
    db_active_connections = _prometheus_query_first(
        platform,
        [
            'sum(mysql_global_status_threads_connected)',
            'sum(pg_stat_database_numbackends)',
        ],
    )
    db_slow_queries = _prometheus_query_first(
        platform,
        [
            'sum(rate(mysql_global_status_slow_queries[5m]))',
            'sum(rate(pg_stat_database_deadlocks[5m]))',
        ],
    )
    redis_hit_rate = _prometheus_query_for_platform(
        platform,
        '100 * (sum(rate(redis_keyspace_hits_total[5m])) / (sum(rate(redis_keyspace_hits_total[5m])) + sum(rate(redis_keyspace_misses_total[5m]))))',
    )
    container_running = _prometheus_query_first(
        platform,
        [
            (
                f'count(count by (id) (container_last_seen{{instance=~"{host_instance_re}",id=~"/docker/.+"}}))'
                if host_instance_re
                else ""
            ),
            (
                f'count(count by (name) (container_last_seen{{instance=~"{host_instance_re}",name!="",image!=""}}))'
                if host_instance_re
                else ""
            ),
            (
                f'sum(engine_daemon_container_states_containers{{instance=~"{host_instance_re}",state="running"}})'
                if host_instance_re
                else ""
            ),
            'count(count by (id) (container_last_seen{id=~"/docker/.+"}))',
            'count(count by (name) (container_last_seen{name!="",image!=""}))',
            'sum(engine_daemon_container_states_containers{state="running"})',
        ],
    )
    up_count = _prometheus_query_first(
        platform,
        [
            f'count(up{{job="node-exporter"{inst_filter}}} == 1)',
            f'count(max by (host) (label_replace(up{{job=~"node-exporter|cadvisor"{inst_filter}}}, "host", "$1", "instance", "([^:]+)(?::.*)?")) == 1)',
            'count(up == 1)',
        ],
    )
    down_count = _prometheus_query_first(
        platform,
        [
            f'count(up{{job="node-exporter"{inst_filter}}} == 0)',
            f'count(max by (host) (label_replace(up{{job=~"node-exporter|cadvisor"{inst_filter}}}, "host", "$1", "instance", "([^:]+)(?::.*)?")) == 0)',
            'count(up == 0)',
        ],
    )
    # 关键逻辑说明(lxl): 运行容器数优先使用 SSH 执行 docker ps 精确统计。
    ssh_container_running = None
    if (not target_host) or (str(target_host).strip() == str(platform.host or "").strip()):
        ssh_container_running = _docker_running_count_via_ssh(platform)
    if ssh_container_running is not None:
        container_running = ssh_container_running

    collected_at = timezone.now()
    metrics = {
        "cpu_usage_percent": _safe_round(cpu_usage, 2),
        "cpu_iowait_percent": _safe_round(cpu_iowait, 2),
        "memory_usage_percent": _safe_round(mem_usage, 2),
        "swap_usage_percent": _safe_round(swap_usage, 2),
        "disk_usage_percent": _safe_round(disk_usage, 2),
        "disk_await_ms": _safe_round(disk_await_ms, 2),
        "network_throughput_mbps": _safe_round(network_throughput_mbps, 2),
        "network_drop_rate": _safe_round(network_drop_rate, 4),
        "network_interfaces": network_interfaces,
        "load1": _safe_round(load1, 2),
        "load5": _safe_round(load5, 2),
        "host_uptime_hours": _safe_round(host_uptime_hours, 1),
        "cpu_cores": _safe_int(cpu_cores),
        "memory_available_gb": _safe_round(memory_available_gb, 2),
        "disk_free_gb": _safe_round(disk_free_gb, 2),
        "disk_read_mbps": _safe_round(disk_read_mbps, 2),
        "disk_write_mbps": _safe_round(disk_write_mbps, 2),
        "network_rx_mbps": _safe_round(network_rx_mbps, 2),
        "network_tx_mbps": _safe_round(network_tx_mbps, 2),
        "tcp_established": _safe_int(tcp_established),
        "tcp_time_wait": _safe_int(tcp_time_wait),
        "process_running": _safe_int(process_running),
        "process_blocked": _safe_int(process_blocked),
        "container_restart_count": _safe_int(container_restart_count),
        "pod_abnormal_count": _safe_int(pod_abnormal_count),
        "api_qps": _safe_round(api_qps, 2),
        "api_p95_ms": _safe_round(api_p95_ms, 2),
        "api_5xx_rate": _safe_round(api_5xx_rate, 2),
        "db_active_connections": _safe_int(db_active_connections),
        "db_slow_queries": _safe_round(db_slow_queries, 3),
        "redis_hit_rate": _safe_round(redis_hit_rate, 2),
        "container_running": _safe_int(container_running),
        "targets_up": _safe_int(up_count),
        "targets_down": _safe_int(down_count),
    }
    _persist_monitor_metric_snapshot(platform, metrics, collected_at=collected_at, scope_host=target_host)

    return metrics, collected_at


def collect_all_running_platforms():
    """遍历所有运行中的平台执行指标采集，返回统计信息。"""
    from autotest.views import _collect_platform_target_hosts

    django.db.close_old_connections()

    platforms = list(
        MonitorPlatform.objects.filter(status=MonitorPlatform.STATUS_RUNNING)
        .exclude(prometheus_url="")
        .exclude(prometheus_url__isnull=True)
    )

    stats = {"total": len(platforms), "success": 0, "failed": 0}

    for platform in platforms:
        try:
            # 采集聚合指标（无 target_host 过滤）
            collect_metrics_for_platform(platform, target_host="")

            # 对集群类型，额外按主机逐一采集
            if platform.platform_type == MonitorPlatform.PLATFORM_TYPE_HOST_CLUSTER:
                hosts = _collect_platform_target_hosts(platform)
                for host in hosts:
                    try:
                        collect_metrics_for_platform(platform, target_host=host)
                    except Exception:
                        logger.exception("采集平台 %s 主机 %s 失败", platform.name, host)

            stats["success"] += 1
        except Exception:
            stats["failed"] += 1
            logger.exception("采集平台 %s 失败", platform.name)

    return stats
