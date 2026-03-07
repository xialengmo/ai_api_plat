# 作者: lxl
# 说明: 业务模块实现。
from django.conf import settings
from django.db import migrations, models


def seed_user_project_access(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    Project = apps.get_model('autotest', 'Project')
    UserProjectAccess = apps.get_model('autotest', 'UserProjectAccess')
    project_ids = list(Project.objects.values_list('id', flat=True))
    if not project_ids:
        return
    rows = []
    for user in User.objects.all().iterator():
        username = str(getattr(user, 'username', '') or '').strip().lower()
        if username == 'admin':
            continue
        for project_id in project_ids:
            rows.append(UserProjectAccess(user_id=user.id, project_id=project_id, is_active=True))
    if rows:
        UserProjectAccess.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('autotest', '0023_scenariodataset_assert_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProjectAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('project', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='user_accesses', to='autotest.project')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='project_accesses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_project_accesses',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='userprojectaccess',
            constraint=models.UniqueConstraint(fields=('user', 'project'), name='uniq_user_project_access'),
        ),
        migrations.RunPython(seed_user_project_access, migrations.RunPython.noop),
    ]
