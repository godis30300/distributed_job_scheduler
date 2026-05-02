-- Demo seed data for PostgreSQL / Log / DB Controller

INSERT INTO users (id, username, password_hash, role, created_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'admin', '$2b$12$demo.admin.hash', 'admin', now()),
    ('00000000-0000-0000-0000-000000000002', 'jielin', '$2b$12$demo.jielin.hash', 'operator', now())
ON CONFLICT (username) DO NOTHING;

INSERT INTO jobs (
    id,
    user_id,
    task_name,
    action_type,
    action_payload,
    schedule_rule,
    status,
    enabled,
    timeout_seconds,
    max_retry,
    next_run_at,
    created_at,
    updated_at
)
VALUES
    (
        '10000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000002',
        'call-health-api',
        'api_call',
        '{"method":"GET","url":"https://example.com/health","headers":{},"body":null}'::jsonb,
        'every:5m',
        'active',
        TRUE,
        60,
        3,
        now(),
        now(),
        now()
    ),
    (
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000002',
        'run-cleanup-script',
        'shell',
        '{"script":"hello.sh","args":[]}'::jsonb,
        'every:10m',
        'active',
        TRUE,
        120,
        2,
        now(),
        now(),
        now()
    )
ON CONFLICT (task_name) DO NOTHING;

INSERT INTO job_runs (
    id,
    job_id,
    user_id,
    status,
    trigger_type,
    retry_count,
    action_payload,
    created_at,
    updated_at
)
VALUES
    (
        '20000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000002',
        'pending',
        'schedule',
        0,
        '{"method":"GET","url":"https://example.com/health","headers":{},"body":null}'::jsonb,
        now(),
        now()
    ),
    (
        '20000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000002',
        'pending',
        'manual',
        0,
        '{"script":"hello.sh","args":[]}'::jsonb,
        now(),
        now()
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO job_logs (id, job_run_id, log_level, stream, message, created_at)
VALUES
    ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'info', 'system', 'demo api_call run created', now()),
    ('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'info', 'system', 'demo shell run created', now())
ON CONFLICT (id) DO NOTHING;

INSERT INTO job_dependencies (id, job_id, depends_on_job_id, required_status, created_at)
VALUES (
    '40000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    'success',
    now()
)
ON CONFLICT (job_id, depends_on_job_id) DO NOTHING;
