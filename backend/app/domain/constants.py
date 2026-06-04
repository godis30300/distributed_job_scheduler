# Centralized domain constants to avoid duplication and satisfy SonarQube requirements.

JOB_ACTION_TYPES = (
    'api_call',
    'shell',
    'python',
    'report',
    'email',
    'backup',
    'fail-test',
    'long-task',
    'api_poll'
)

JOB_RUN_STATUSES = (
    'pending',
    'running',
    'success',
    'failed',
    'timeout',
    'canceled',
    'awaiting_result'
)

JOB_STATUSES = (
    'enabled',
    'active',
    'paused',
    'disabled',
    'deleted'
)

TRIGGER_TYPES = (
    'schedule',
    'manual',
    'api',
    'retry',
    'dependency'
)

LOG_LEVELS = (
    'debug',
    'info',
    'warning',
    'error'
)

LOG_STREAMS = (
    'stdout',
    'stderr',
    'system'
)
