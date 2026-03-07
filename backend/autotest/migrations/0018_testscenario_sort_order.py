# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autotest", "0017_apimodule_parent_and_tree_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="testscenario",
            name="sort_order",
            field=models.IntegerField(default=0, verbose_name="排序"),
        ),
        migrations.AlterModelOptions(
            name="testscenario",
            options={"ordering": ["sort_order", "id"]},
        ),
    ]

