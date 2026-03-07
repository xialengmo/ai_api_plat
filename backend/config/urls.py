# 作者: lxl
# 说明: 业务模块实现。
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("autotest.urls")),
]

