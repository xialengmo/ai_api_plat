# 作者: lxl
# 说明: 资源监控平台模型迁移。
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0026_operationauditlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorPlatform",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True, verbose_name="Platform Name")),
                ("host", models.CharField(max_length=255, verbose_name="Host")),
                ("ssh_port", models.IntegerField(default=22, verbose_name="SSH Port")),
                ("ssh_username", models.CharField(max_length=128, verbose_name="SSH Username")),
                ("ssh_password", models.CharField(blank=True, max_length=255, null=True, verbose_name="SSH Password")),
                (
                    "deploy_mode",
                    models.CharField(
                        choices=[("online", "Online"), ("offline", "Offline")],
                        default="online",
                        max_length=16,
                        verbose_name="Deploy Mode",
                    ),
                ),
                ("offline_package_name", models.CharField(blank=True, max_length=255, null=True, verbose_name="Offline Package Name")),
                ("offline_package_path", models.CharField(blank=True, max_length=512, null=True, verbose_name="Offline Package Path")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("deploying", "Deploying"), ("running", "Running"), ("failed", "Failed")],
                        default="pending",
                        max_length=16,
                        verbose_name="Status",
                    ),
                ),
                ("prometheus_url", models.CharField(blank=True, max_length=255, null=True, verbose_name="Prometheus URL")),
                ("grafana_url", models.CharField(blank=True, max_length=255, null=True, verbose_name="Grafana URL")),
                ("alertmanager_url", models.CharField(blank=True, max_length=255, null=True, verbose_name="Alertmanager URL")),
                ("deploy_logs", models.JSONField(blank=True, default=list, null=True, verbose_name="Deploy Logs")),
                ("last_error", models.CharField(blank=True, max_length=500, null=True, verbose_name="Last Error")),
                ("last_deployed_at", models.DateTimeField(blank=True, null=True, verbose_name="Last Deployed At")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="monitor_platforms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "monitor_platforms",
                "ordering": ["-id"],
            },
        ),
    ]
