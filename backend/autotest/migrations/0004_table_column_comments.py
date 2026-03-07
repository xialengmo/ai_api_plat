# 作者: lxl
# 说明: 业务模块实现。
from django.db import migrations


COMMENT_SQL = [
    # test_cases
    "ALTER TABLE `test_cases` COMMENT='接口定义表：存储可复用的单接口测试配置';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `name` varchar(128) NOT NULL COMMENT '接口名称';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `description` varchar(255) NULL COMMENT '接口描述';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `base_url` varchar(255) NOT NULL COMMENT '服务基础地址';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `path` varchar(255) NOT NULL COMMENT '接口路径';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `method` varchar(16) NOT NULL COMMENT 'HTTP方法';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `headers` json NULL COMMENT '请求头JSON';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `params` json NULL COMMENT '查询参数JSON';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `body_json` json NULL COMMENT '请求体JSON';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `body_text` longtext NULL COMMENT '请求体文本';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `timeout_seconds` int NOT NULL DEFAULT 10 COMMENT '超时时间(秒)';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `assert_status` int NULL COMMENT '断言状态码';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `assert_contains` varchar(255) NULL COMMENT '断言响应包含文本';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `created_at` datetime(6) NOT NULL COMMENT '创建时间';",
    "ALTER TABLE `test_cases` MODIFY COLUMN `updated_at` datetime(6) NOT NULL COMMENT '更新时间';",
    # run_histories
    "ALTER TABLE `run_histories` COMMENT='单接口执行历史表：记录每次接口执行结果';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `test_case_id` bigint NOT NULL COMMENT '所属接口ID';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `success` int NOT NULL DEFAULT 0 COMMENT '是否成功(1成功0失败)';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `status_code` int NULL COMMENT '响应状态码';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `response_time_ms` int NULL COMMENT '响应耗时(毫秒)';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `error_message` varchar(255) NULL COMMENT '错误信息';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `response_body` longtext NULL COMMENT '响应体(截断存储)';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `assertion_result` varchar(255) NULL COMMENT '断言结果摘要';",
    "ALTER TABLE `run_histories` MODIFY COLUMN `created_at` datetime(6) NOT NULL COMMENT '创建时间';",
    # test_scenarios
    "ALTER TABLE `test_scenarios` COMMENT='测试场景表：由多个步骤串联形成业务流程';",
    "ALTER TABLE `test_scenarios` MODIFY COLUMN `name` varchar(128) NOT NULL COMMENT '场景名称';",
    "ALTER TABLE `test_scenarios` MODIFY COLUMN `description` varchar(255) NULL COMMENT '场景描述';",
    "ALTER TABLE `test_scenarios` MODIFY COLUMN `stop_on_failure` tinyint(1) NOT NULL COMMENT '失败即停止';",
    "ALTER TABLE `test_scenarios` MODIFY COLUMN `created_at` datetime(6) NOT NULL COMMENT '创建时间';",
    "ALTER TABLE `test_scenarios` MODIFY COLUMN `updated_at` datetime(6) NOT NULL COMMENT '更新时间';",
    # scenario_steps
    "ALTER TABLE `scenario_steps` COMMENT='场景步骤表：定义步骤顺序、参数传递、提取与断言规则';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `scenario_id` bigint NOT NULL COMMENT '所属场景ID';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `step_order` int NOT NULL DEFAULT 1 COMMENT '步骤顺序';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `step_name` varchar(128) NOT NULL COMMENT '步骤名称';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `test_case_id` bigint NOT NULL COMMENT '引用接口ID';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `enabled` tinyint(1) NOT NULL COMMENT '是否启用';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `continue_on_fail` tinyint(1) NOT NULL COMMENT '失败后是否继续';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `overrides` json NULL COMMENT '步骤请求覆盖配置';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `extract_rules` json NULL COMMENT '变量提取规则';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `preconditions` json NULL COMMENT '前置条件规则';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `assertions` json NULL COMMENT '断言规则';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `created_at` datetime(6) NOT NULL COMMENT '创建时间';",
    "ALTER TABLE `scenario_steps` MODIFY COLUMN `updated_at` datetime(6) NOT NULL COMMENT '更新时间';",
    # scenario_run_histories
    "ALTER TABLE `scenario_run_histories` COMMENT='场景执行历史表：记录串联场景运行结果和上下文快照';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `scenario_id` bigint NOT NULL COMMENT '所属场景ID';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `success` int NOT NULL DEFAULT 0 COMMENT '是否成功(1成功0失败)';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `duration_ms` int NULL COMMENT '场景总耗时(毫秒)';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `results` json NULL COMMENT '步骤执行明细';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `context_snapshot` json NULL COMMENT '变量上下文快照';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `error_message` varchar(255) NULL COMMENT '错误信息';",
    "ALTER TABLE `scenario_run_histories` MODIFY COLUMN `created_at` datetime(6) NOT NULL COMMENT '创建时间';",
]


REVERSE_SQL = [
    "ALTER TABLE `test_cases` COMMENT='';",
    "ALTER TABLE `run_histories` COMMENT='';",
    "ALTER TABLE `test_scenarios` COMMENT='';",
    "ALTER TABLE `scenario_steps` COMMENT='';",
    "ALTER TABLE `scenario_run_histories` COMMENT='';",
]


def apply_comments(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for sql in COMMENT_SQL:
            cursor.execute(sql)


def revert_comments(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for sql in REVERSE_SQL:
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("autotest", "0003_step_rules"),
    ]

    operations = [
        migrations.RunPython(apply_comments, reverse_code=revert_comments),
    ]
