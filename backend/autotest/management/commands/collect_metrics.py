# 作者: lxl
# 说明: 后台定时采集监控指标的 management command。
#       启动方式: python manage.py collect_metrics [--interval 60] [--once]
import logging
import os
import signal
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger("autotest.metrics_collector")


class Command(BaseCommand):
    help = "后台定时采集所有运行中平台的监控指标"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="采集间隔（秒），默认 60，可被环境变量 METRICS_COLLECT_INTERVAL 覆盖",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="仅执行一次采集后退出（用于测试或 cron 调度）",
        )

    def handle(self, *args, **options):
        from autotest.metrics_collector import collect_all_running_platforms

        interval = options["interval"]
        run_once = options["once"]

        env_interval = os.getenv("METRICS_COLLECT_INTERVAL")
        if env_interval:
            try:
                interval = int(env_interval)
            except ValueError:
                pass

        if os.getenv("METRICS_COLLECT_ENABLED", "true").lower() == "false":
            self.stdout.write("指标采集已通过 METRICS_COLLECT_ENABLED=false 禁用")
            return

        shutdown = False

        def _signal_handler(signum, frame):
            nonlocal shutdown
            shutdown = True

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        self.stdout.write(f"指标采集器启动（间隔={interval}s，单次={run_once}）")
        logger.info("指标采集器启动（间隔=%ds，单次=%s）", interval, run_once)

        while not shutdown:
            cycle_start = time.monotonic()
            try:
                stats = collect_all_running_platforms()
                self.stdout.write(
                    f"采集完成: 共 {stats['total']} 个平台，"
                    f"成功 {stats['success']}，失败 {stats['failed']}"
                )
                logger.info("采集完成: %s", stats)
            except Exception:
                logger.exception("采集周期出现未预期的异常")

            if run_once:
                break

            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0, interval - elapsed)
            slept = 0.0
            while slept < sleep_time and not shutdown:
                chunk = min(1.0, sleep_time - slept)
                time.sleep(chunk)
                slept += chunk

        self.stdout.write("指标采集器已停止")
        logger.info("指标采集器已停止")
