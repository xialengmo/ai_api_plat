from django.db import migrations, models
import django.db.models.deletion


def populate_scenario_project(apps, schema_editor):
    TestScenario = apps.get_model("autotest", "TestScenario")
    ApiModule = apps.get_model("autotest", "ApiModule")

    module_project_map = dict(ApiModule.objects.values_list("id", "project_id"))
    missing_ids = []
    for scenario in TestScenario.objects.all().only("id", "module_id", "project_id"):
        project_id = module_project_map.get(scenario.module_id)
        if not project_id:
            missing_ids.append(int(scenario.id))
            continue
        TestScenario.objects.filter(id=scenario.id).update(project_id=project_id)

    if missing_ids:
        raise RuntimeError(f"TestScenario missing module/project mapping: {missing_ids[:20]}")


class Migration(migrations.Migration):

    dependencies = [
        ("autotest", "0029_monitormetricsnapshot_scope_host_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="testscenario",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="test_scenarios",
                to="autotest.project",
            ),
        ),
        migrations.RunPython(populate_scenario_project, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="testscenario",
            name="name",
            field=models.CharField(max_length=128, verbose_name="Scenario Name"),
        ),
        migrations.AlterField(
            model_name="testscenario",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="test_scenarios",
                to="autotest.project",
            ),
        ),
        migrations.AddConstraint(
            model_name="apimodule",
            constraint=models.UniqueConstraint(
                fields=("project", "parent", "name"),
                name="uniq_api_module_name_in_project_parent",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="apimodule",
            name="uniq_api_module_name_in_project",
        ),
        migrations.AddConstraint(
            model_name="testscenario",
            constraint=models.UniqueConstraint(
                fields=("project", "name"),
                name="uniq_test_scenario_name_in_project",
            ),
        ),
    ]
