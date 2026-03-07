# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autotest", "0022_testscenario_param_retry_count_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_enabled",
            field=models.BooleanField(default=False, verbose_name="Assert Enabled"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_header_expected",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Assert Header Expected"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_header_jsonpath",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Assert Header JSONPath"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_response_expected",
            field=models.TextField(blank=True, null=True, verbose_name="Assert Response Expected"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_response_jsonpath",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Assert Response JSONPath"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_status_code",
            field=models.IntegerField(blank=True, null=True, verbose_name="Assert Status Code"),
        ),
        migrations.AddField(
            model_name="scenariodataset",
            name="assert_targets",
            field=models.JSONField(blank=True, default=list, null=True, verbose_name="Assert Targets"),
        ),
    ]

