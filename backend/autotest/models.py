# 作者: lxl
# 说明: 业务模块实现。
from django.db import models
from django.conf import settings


class Project(models.Model):
    name = models.CharField("Project Name", max_length=128, unique=True)
    description = models.CharField("Project Description", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.name


class UserProjectAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_accesses",
        db_index=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="user_accesses",
        db_index=True,
    )
    is_active = models.BooleanField("Is Active", default=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "user_project_accesses"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "project"], name="uniq_user_project_access")
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.project_id}"


class ProjectEnvironment(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="environments",
        db_index=True,
    )
    name = models.CharField("Environment Name", max_length=128)
    description = models.CharField("Environment Description", max_length=255, blank=True, null=True)
    base_url = models.CharField("Base URL", max_length=255)
    variables = models.JSONField("Variables", blank=True, null=True)
    default_headers = models.JSONField("Default Headers", blank=True, null=True)
    is_active = models.BooleanField("Is Active", default=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "project_environments"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_env_name_in_project")
        ]

    def __str__(self) -> str:
        return self.name


class GlobalVariable(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="global_variables",
        db_index=True,
    )
    name = models.CharField("Variable Name", max_length=128)
    value = models.JSONField("Variable Value", blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "global_variables"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_global_var_name_in_project")
        ]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.name}"


class ApiModule(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_modules",
        db_index=True,
    )
    name = models.CharField("Module Name", max_length=128)
    description = models.CharField("Module Description", max_length=255, blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        blank=True,
        null=True,
        db_index=True,
    )
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "api_modules"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "parent", "name"],
                name="uniq_api_module_name_in_project_parent",
            )
        ]

    def __str__(self) -> str:
        return self.name


class ScenarioDataSet(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="scenario_data_sets",
        db_index=True,
    )
    module = models.ForeignKey(
        ApiModule,
        on_delete=models.SET_NULL,
        related_name="scenario_data_sets",
        db_index=True,
        blank=True,
        null=True,
    )
    name = models.CharField("Data Set Name", max_length=128)
    description = models.CharField("Data Set Description", max_length=255, blank=True, null=True)
    source_type = models.CharField("Source Type", max_length=16, default="table")
    data_rows = models.JSONField("Table Rows", blank=True, null=True)
    raw_text = models.TextField("Raw Text", blank=True, null=True)
    enabled = models.BooleanField("Enabled", default=True)
    assert_enabled = models.BooleanField("Assert Enabled", default=False)
    assert_targets = models.JSONField("Assert Targets", blank=True, null=True, default=list)
    assert_status_code = models.IntegerField("Assert Status Code", blank=True, null=True)
    assert_header_jsonpath = models.CharField("Assert Header JSONPath", max_length=255, blank=True, null=True)
    assert_header_expected = models.CharField("Assert Header Expected", max_length=255, blank=True, null=True)
    assert_response_jsonpath = models.CharField("Assert Response JSONPath", max_length=255, blank=True, null=True)
    assert_response_expected = models.TextField("Assert Response Expected", blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "scenario_data_sets"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_dataset_name_in_project")
        ]

    def __str__(self) -> str:
        return self.name


class TestCase(models.Model):
    name = models.CharField("Case Name", max_length=128)
    description = models.CharField("Case Description", max_length=255, blank=True, null=True)
    base_url = models.CharField("Base URL", max_length=255)
    path = models.CharField("Path", max_length=255)
    method = models.CharField("Method", max_length=16, default="GET")
    headers = models.JSONField("Headers", blank=True, null=True)
    params = models.JSONField("Params", blank=True, null=True)
    body_json = models.JSONField("Body JSON", blank=True, null=True)
    body_text = models.TextField("Body Text", blank=True, null=True)
    timeout_seconds = models.IntegerField("Timeout Seconds", default=1)
    verify_ssl = models.BooleanField("Verify SSL", default=False)
    assert_status = models.IntegerField("Assert Status", blank=True, null=True)
    assert_contains = models.CharField("Assert Contains", max_length=255, blank=True, null=True)
    custom_assertions = models.JSONField("Custom Assertions", blank=True, null=True)
    environment = models.ForeignKey(
        ProjectEnvironment,
        on_delete=models.SET_NULL,
        related_name="test_cases",
        db_index=True,
        blank=True,
        null=True,
    )
    module = models.ForeignKey(
        ApiModule,
        on_delete=models.SET_NULL,
        related_name="test_cases",
        db_index=True,
        blank=True,
        null=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="test_cases",
        db_index=True,
    )
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "test_cases"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_test_case_name_in_project")
        ]

    def __str__(self) -> str:
        return self.name


class RunHistory(models.Model):
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="run_histories", db_index=True
    )
    success = models.IntegerField("Success", default=0)
    status_code = models.IntegerField("Status Code", blank=True, null=True)
    response_time_ms = models.IntegerField("Response Time Ms", blank=True, null=True)
    error_message = models.CharField("Error Message", max_length=255, blank=True, null=True)
    request_snapshot = models.JSONField("Request Snapshot", blank=True, null=True)
    response_headers = models.JSONField("Response Headers", blank=True, null=True)
    response_content_type = models.CharField("Response Content Type", max_length=255, blank=True, null=True)
    response_body = models.TextField("Response Body", blank=True, null=True)
    assertion_result = models.CharField("Assertion Result", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)

    class Meta:
        db_table = "run_histories"
        ordering = ["-id"]


class TestScenario(models.Model):
    name = models.CharField("Scenario Name", max_length=128)
    description = models.CharField("Scenario Description", max_length=255, blank=True, null=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="test_scenarios",
        db_index=True,
    )
    module = models.ForeignKey(
        ApiModule,
        on_delete=models.SET_NULL,
        related_name="test_scenarios",
        blank=True,
        null=True,
        db_index=True,
    )
    param_enabled = models.BooleanField("Param Enabled", default=False)
    data_set = models.ForeignKey(
        ScenarioDataSet,
        on_delete=models.SET_NULL,
        related_name="test_scenarios",
        blank=True,
        null=True,
        db_index=True,
    )
    data_mode = models.CharField("Data Run Mode", max_length=16, default="all")
    data_pick = models.CharField("Data Pick Config", max_length=255, blank=True, null=True)
    param_retry_count = models.IntegerField("Param Retry Count", default=0)
    sort_order = models.IntegerField("Sort Order", default=0)
    stop_on_failure = models.BooleanField("Stop On Failure", default=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "test_scenarios"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="uniq_test_scenario_name_in_project")
        ]

    def __str__(self) -> str:
        return self.name


class ScenarioStep(models.Model):
    scenario = models.ForeignKey(
        TestScenario, on_delete=models.CASCADE, related_name="steps", db_index=True
    )
    step_order = models.IntegerField("Step Order", default=1)
    step_name = models.CharField("Step Name", max_length=128)
    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="scenario_steps", db_index=True
    )
    enabled = models.BooleanField("Enabled", default=True)
    continue_on_fail = models.BooleanField("Continue On Fail", default=False)
    overrides = models.JSONField("Overrides", blank=True, null=True)
    extract_rules = models.JSONField("Extract Rules", blank=True, null=True)
    preconditions = models.JSONField("Preconditions", blank=True, null=True)
    assertions = models.JSONField("Assertions", blank=True, null=True)
    pre_processors = models.JSONField("Pre Processors", blank=True, null=True)
    post_processors = models.JSONField("Post Processors", blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "scenario_steps"
        ordering = ["step_order", "id"]

    def __str__(self) -> str:
        return f"{self.scenario_id}-{self.step_order}-{self.step_name}"


class ScenarioRunHistory(models.Model):
    scenario = models.ForeignKey(
        TestScenario, on_delete=models.CASCADE, related_name="run_histories", db_index=True
    )
    success = models.IntegerField("Success", default=0)
    duration_ms = models.IntegerField("Duration Ms", blank=True, null=True)
    results = models.JSONField("Step Results", blank=True, null=True)
    iterations = models.JSONField("Iteration Results", blank=True, null=True)
    context_snapshot = models.JSONField("Context Snapshot", blank=True, null=True)
    error_message = models.CharField("Error Message", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True)

    class Meta:
        db_table = "scenario_run_histories"
        ordering = ["-id"]


class LoginAuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="login_audit_logs",
        db_index=True,
        blank=True,
        null=True,
    )
    username = models.CharField("Username", max_length=150, blank=True, null=True)
    success = models.IntegerField("Success", default=0)
    detail = models.CharField("Detail", max_length=255, blank=True, null=True)
    ip = models.CharField("IP", max_length=64, blank=True, null=True)
    user_agent = models.CharField("User Agent", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "login_audit_logs"
        ordering = ["-id"]


class OperationAuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="operation_audit_logs",
        db_index=True,
        blank=True,
        null=True,
    )
    username = models.CharField("Username", max_length=150, blank=True, null=True)
    method = models.CharField("Method", max_length=8)
    path = models.CharField("Path", max_length=255)
    status_code = models.IntegerField("Status Code", blank=True, null=True)
    success = models.IntegerField("Success", default=0)
    detail = models.CharField("Detail", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "operation_audit_logs"
        ordering = ["-id"]


class MonitorPlatform(models.Model):
    PLATFORM_TYPE_SINGLE = "single"
    PLATFORM_TYPE_HOST_CLUSTER = "host_cluster"
    PLATFORM_TYPE_CHOICES = (
        (PLATFORM_TYPE_SINGLE, "Single"),
        (PLATFORM_TYPE_HOST_CLUSTER, "Host Cluster"),
    )

    DEPLOY_MODE_ONLINE = "online"
    DEPLOY_MODE_OFFLINE = "offline"
    DEPLOY_MODE_CHOICES = (
        (DEPLOY_MODE_ONLINE, "Online"),
        (DEPLOY_MODE_OFFLINE, "Offline"),
    )

    STATUS_PENDING = "pending"
    STATUS_DEPLOYING = "deploying"
    STATUS_RUNNING = "running"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_DEPLOYING, "Deploying"),
        (STATUS_RUNNING, "Running"),
        (STATUS_FAILED, "Failed"),
    )

    name = models.CharField("Platform Name", max_length=128, unique=True)
    platform_type = models.CharField(
        "Platform Type",
        max_length=24,
        choices=PLATFORM_TYPE_CHOICES,
        default=PLATFORM_TYPE_SINGLE,
    )
    host = models.CharField("Host", max_length=255)
    ssh_port = models.IntegerField("SSH Port", default=22)
    ssh_username = models.CharField("SSH Username", max_length=128)
    ssh_password = models.CharField("SSH Password", max_length=255, blank=True, null=True)
    deploy_mode = models.CharField(
        "Deploy Mode",
        max_length=16,
        choices=DEPLOY_MODE_CHOICES,
        default=DEPLOY_MODE_ONLINE,
    )
    offline_package_name = models.CharField("Offline Package Name", max_length=255, blank=True, null=True)
    offline_package_path = models.CharField("Offline Package Path", max_length=512, blank=True, null=True)
    status = models.CharField(
        "Status",
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    prometheus_url = models.CharField("Prometheus URL", max_length=255, blank=True, null=True)
    grafana_url = models.CharField("Grafana URL", max_length=255, blank=True, null=True)
    alertmanager_url = models.CharField("Alertmanager URL", max_length=255, blank=True, null=True)
    deploy_logs = models.JSONField("Deploy Logs", blank=True, null=True, default=list)
    last_error = models.CharField("Last Error", max_length=500, blank=True, null=True)
    last_deployed_at = models.DateTimeField("Last Deployed At", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="monitor_platforms",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "monitor_platforms"
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.name


class MonitorMetricSnapshot(models.Model):
    platform = models.ForeignKey(
        MonitorPlatform,
        on_delete=models.CASCADE,
        related_name="metric_snapshots",
        db_index=True,
    )
    metrics = models.JSONField("Metrics", blank=True, null=True, default=dict)
    scope_host = models.CharField("Scope Host", max_length=255, blank=True, default="", db_index=True)
    collected_at = models.DateTimeField("Collected At", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "monitor_metric_snapshots"
        ordering = ["-collected_at", "-id"]


class MonitorPlatformTarget(models.Model):
    platform = models.ForeignKey(
        MonitorPlatform,
        on_delete=models.CASCADE,
        related_name="monitor_targets",
        db_index=True,
    )
    name = models.CharField("Target Name", max_length=128, blank=True, null=True)
    host = models.CharField("Target Host", max_length=255)
    node_exporter_port = models.IntegerField("Node Exporter Port", default=9100)
    cadvisor_port = models.IntegerField("cAdvisor Port", default=8080)
    enabled = models.BooleanField("Enabled", default=True)
    sort_order = models.IntegerField("Sort Order", default=0)
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)

    class Meta:
        db_table = "monitor_platform_targets"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "host"], name="uniq_monitor_target_platform_host"),
        ]

    def __str__(self) -> str:
        return f"{self.platform_id}:{self.host}"
