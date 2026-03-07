# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models
import django.db.models.deletion


def init_default_project(apps, schema_editor):
    Project = apps.get_model("autotest", "Project")
    TestCase = apps.get_model("autotest", "TestCase")
    default_project, _ = Project.objects.get_or_create(
        name="默认项目",
        defaults={"description": "系统自动创建"},
    )
    TestCase.objects.filter(project__isnull=True).update(project=default_project)


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0004_table_column_comments"),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True, verbose_name="项目名称")),
                ("description", models.CharField(blank=True, max_length=255, null=True, verbose_name="项目描述")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"db_table": "projects", "ordering": ["-id"]},
        ),
        migrations.AddField(
            model_name="testcase",
            name="project",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="test_cases",
                to="autotest.project",
            ),
        ),
        migrations.RunPython(init_default_project, reverse_code=migrations.RunPython.noop),
    ]
