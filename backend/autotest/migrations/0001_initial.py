# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True, verbose_name="用例名称")),
                ("description", models.CharField(blank=True, max_length=255, null=True, verbose_name="描述")),
                ("base_url", models.CharField(max_length=255, verbose_name="基础地址")),
                ("path", models.CharField(max_length=255, verbose_name="路径")),
                ("method", models.CharField(default="GET", max_length=16, verbose_name="请求方法")),
                ("headers", models.JSONField(blank=True, null=True, verbose_name="请求头")),
                ("params", models.JSONField(blank=True, null=True, verbose_name="查询参数")),
                ("body_json", models.JSONField(blank=True, null=True, verbose_name="JSON请求体")),
                ("body_text", models.TextField(blank=True, null=True, verbose_name="文本请求体")),
                ("timeout_seconds", models.IntegerField(default=10, verbose_name="超时秒数")),
                ("assert_status", models.IntegerField(blank=True, null=True, verbose_name="断言状态码")),
                ("assert_contains", models.CharField(blank=True, max_length=255, null=True, verbose_name="断言文本包含")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"db_table": "test_cases", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="RunHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("success", models.IntegerField(default=0, verbose_name="是否成功")),
                ("status_code", models.IntegerField(blank=True, null=True, verbose_name="响应状态码")),
                ("response_time_ms", models.IntegerField(blank=True, null=True, verbose_name="响应耗时毫秒")),
                ("error_message", models.CharField(blank=True, max_length=255, null=True, verbose_name="错误信息")),
                ("response_body", models.TextField(blank=True, null=True, verbose_name="响应体")),
                ("assertion_result", models.CharField(blank=True, max_length=255, null=True, verbose_name="断言结果")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "test_case",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="run_histories",
                        to="autotest.testcase",
                    ),
                ),
            ],
            options={"db_table": "run_histories", "ordering": ["-id"]},
        ),
    ]

