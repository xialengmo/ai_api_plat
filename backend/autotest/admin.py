# 作者: lxl
# 说明: 业务模块实现。
from django.contrib import admin

from autotest.models import RunHistory, TestCase

admin.site.register(TestCase)
admin.site.register(RunHistory)

