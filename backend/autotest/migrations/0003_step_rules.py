# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0002_scenario_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariostep",
            name="assertions",
            field=models.JSONField(blank=True, null=True, verbose_name="断言规则"),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="preconditions",
            field=models.JSONField(blank=True, null=True, verbose_name="前置条件规则"),
        ),
    ]

