# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models
import django.db.models.deletion


def fill_null_project(apps, schema_editor):
    Project = apps.get_model("autotest", "Project")
    TestCase = apps.get_model("autotest", "TestCase")
    default_project, _ = Project.objects.get_or_create(
        name="默认项目",
        defaults={"description": "系统自动创建"},
    )
    TestCase.objects.filter(project__isnull=True).update(project=default_project)


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0005_project_support"),
    ]

    operations = [
        migrations.RunPython(fill_null_project, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="testcase",
            name="name",
            field=models.CharField(max_length=128, verbose_name="用例名称"),
        ),
        migrations.AlterField(
            model_name="testcase",
            name="project",
            field=models.ForeignKey(
                db_index=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="test_cases",
                to="autotest.project",
            ),
        ),
        migrations.AddConstraint(
            model_name="testcase",
            constraint=models.UniqueConstraint(
                fields=("project", "name"),
                name="uniq_test_case_name_in_project",
            ),
        ),
    ]
