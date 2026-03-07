from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("autotest", "0028_monitormetricsnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitormetricsnapshot",
            name="scope_host",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255, verbose_name="Scope Host"),
        ),
        migrations.AddField(
            model_name="monitorplatform",
            name="platform_type",
            field=models.CharField(
                choices=[("single", "Single"), ("host_cluster", "Host Cluster")],
                default="single",
                max_length=24,
                verbose_name="Platform Type",
            ),
        ),
        migrations.CreateModel(
            name="MonitorPlatformTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=128, null=True, verbose_name="Target Name")),
                ("host", models.CharField(max_length=255, verbose_name="Target Host")),
                ("node_exporter_port", models.IntegerField(default=9100, verbose_name="Node Exporter Port")),
                ("cadvisor_port", models.IntegerField(default=8080, verbose_name="cAdvisor Port")),
                ("enabled", models.BooleanField(default=True, verbose_name="Enabled")),
                ("sort_order", models.IntegerField(default=0, verbose_name="Sort Order")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                (
                    "platform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monitor_targets",
                        to="autotest.monitorplatform",
                    ),
                ),
            ],
            options={
                "db_table": "monitor_platform_targets",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="monitorplatformtarget",
            constraint=models.UniqueConstraint(fields=("platform", "host"), name="uniq_monitor_target_platform_host"),
        ),
    ]
