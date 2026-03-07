from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("autotest", "0027_monitorplatform"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorMetricSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("metrics", models.JSONField(blank=True, default=dict, null=True, verbose_name="Metrics")),
                ("collected_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Collected At")),
                (
                    "platform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metric_snapshots",
                        to="autotest.monitorplatform",
                    ),
                ),
            ],
            options={
                "db_table": "monitor_metric_snapshots",
                "ordering": ["-collected_at", "-id"],
            },
        ),
    ]
