-- Demo seed data for PostgreSQL / Log / DB Controller

INSERT INTO users (id, username, email, password_hash, role, created_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'admin', 'admin@example.com', '$2b$12$idUia.TknmJX2Seo2BNgvOpRWjixQLE7h5wQPiMHCuM8l6aBYa9ra', 'admin', now()),
    ('00000000-0000-0000-0000-000000000002', 'jielin', 'jielin@example.com', '$2b$12$RVKJAsDuqypRy48usuWEoOhz/DRHdW9.noqq8nrd8SdUwGqFDYrQW', 'operator', now())
ON CONFLICT (username) DO NOTHING;

INSERT INTO jobs (
    id,
    user_id,
    name,
    task_name,
    task_type,
    script,
    working_dir,
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
        'call-health-api',
        'api_call',
        NULL,
        NULL,
        'api_call',
        '{"method":"GET","url":"http://backend:8000/api/system/health","headers":{},"body":null}'::jsonb,
        'every:5m',
        'enabled',
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
        'run-cleanup-script',
        'shell',
        'hello.sh',
        '/tmp/job-scheduler-work',
        'shell',
        '{"script":"hello.sh","args":[]}'::jsonb,
        'every:10m',
        'enabled',
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
    triggered_by,
    retry_count,
    task_type,
    script,
    working_dir,
    action_type,
    action_payload,
    timeout_seconds,
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
        'schedule',
        0,
        'api_call',
        NULL,
        NULL,
        'api_call',
        '{"method":"GET","url":"http://backend:8000/api/system/health","headers":{},"body":null}'::jsonb,
        60,
        now(),
        now()
    ),
    (
        '20000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000002',
        'pending',
        'manual',
        'manual',
        0,
        'shell',
        'hello.sh',
        '/tmp/job-scheduler-work',
        'shell',
        '{"script":"hello.sh","args":[]}'::jsonb,
        120,
        now(),
        now()
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO job_logs (id, job_run_id, log_level, stream, message, created_at)
VALUES
    ('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'info', 'system', 'demo api_call run created with action snapshot', now()),
    ('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'info', 'system', 'demo shell run created with action snapshot', now())
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
