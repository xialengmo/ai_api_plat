# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TestScenario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True, verbose_name="场景名称")),
                ("description", models.CharField(blank=True, max_length=255, null=True, verbose_name="场景描述")),
                ("stop_on_failure", models.BooleanField(default=True, verbose_name="失败即停止")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"db_table": "test_scenarios", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="ScenarioStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_order", models.IntegerField(default=1, verbose_name="步骤顺序")),
                ("step_name", models.CharField(max_length=128, verbose_name="步骤名称")),
                ("enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("continue_on_fail", models.BooleanField(default=False, verbose_name="失败继续")),
                ("overrides", models.JSONField(blank=True, null=True, verbose_name="覆盖配置")),
                ("extract_rules", models.JSONField(blank=True, null=True, verbose_name="变量提取规则")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "scenario",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="autotest.testscenario",
                    ),
                ),
                (
                    "test_case",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scenario_steps",
                        to="autotest.testcase",
                    ),
                ),
            ],
            options={"db_table": "scenario_steps", "ordering": ["step_order", "id"]},
        ),
        migrations.CreateModel(
            name="ScenarioRunHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("success", models.IntegerField(default=0, verbose_name="是否成功")),
                ("duration_ms", models.IntegerField(blank=True, null=True, verbose_name="总耗时毫秒")),
                ("results", models.JSONField(blank=True, null=True, verbose_name="步骤执行结果")),
                ("context_snapshot", models.JSONField(blank=True, null=True, verbose_name="变量快照")),
                ("error_message", models.CharField(blank=True, max_length=255, null=True, verbose_name="错误信息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "scenario",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="run_histories",
                        to="autotest.testscenario",
                    ),
                ),
            ],
            options={"db_table": "scenario_run_histories", "ordering": ["-id"]},
        ),
    ]

