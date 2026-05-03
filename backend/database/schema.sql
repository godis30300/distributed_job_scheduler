-- PostgreSQL schema for Distributed Asynchronous Job Scheduler
-- Owner: 杰霖｜PostgreSQL / Log / DB Controller

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    task_name VARCHAR(120) NOT NULL UNIQUE,
    action_type VARCHAR(40) NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    schedule_rule VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    max_retry INTEGER NOT NULL DEFAULT 3,
    description TEXT,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_jobs_action_type CHECK (action_type IN ('api_call', 'shell', 'report', 'email', 'backup', 'fail-test', 'long-task')),
    CONSTRAINT ck_jobs_status CHECK (status IN ('enabled', 'active', 'paused', 'disabled', 'deleted')),
    CONSTRAINT ck_jobs_timeout_positive CHECK (timeout_seconds > 0),
    CONSTRAINT ck_jobs_max_retry_nonnegative CHECK (max_retry >= 0)
);

CREATE TABLE IF NOT EXISTS job_runs (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    trigger_type VARCHAR(32) NOT NULL DEFAULT 'schedule',
    triggered_by VARCHAR(80),
    worker_id VARCHAR(80),
    locked_by VARCHAR(80),
    locked_until TIMESTAMPTZ,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    action_payload JSONB,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_runs_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled')),
    CONSTRAINT ck_job_runs_retry_count_nonnegative CHECK (retry_count >= 0)
);

CREATE TABLE IF NOT EXISTS job_logs (
    id VARCHAR(36) PRIMARY KEY,
    job_run_id VARCHAR(36) NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    log_level VARCHAR(20) NOT NULL DEFAULT 'info',
    stream VARCHAR(20) NOT NULL DEFAULT 'system',
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_logs_level CHECK (log_level IN ('debug', 'info', 'warning', 'error')),
    CONSTRAINT ck_job_logs_stream CHECK (stream IN ('stdout', 'stderr', 'system'))
);

CREATE TABLE IF NOT EXISTS job_dependencies (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    depends_on_job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    required_status VARCHAR(32) NOT NULL DEFAULT 'success',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_dependencies_pair UNIQUE (job_id, depends_on_job_id),
    CONSTRAINT ck_job_dependencies_not_self CHECK (job_id <> depends_on_job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_jobs_next_run_at ON jobs(next_run_at);
CREATE INDEX IF NOT EXISTS idx_jobs_task_name ON jobs(task_name);

CREATE INDEX IF NOT EXISTS idx_job_runs_status_created_at ON job_runs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_job_id ON job_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_id ON job_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_locked_until ON job_runs(locked_until);

CREATE INDEX IF NOT EXISTS idx_job_logs_run_created_at ON job_logs(job_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_logs_level_created_at ON job_logs(log_level, created_at);

CREATE INDEX IF NOT EXISTS idx_job_dependencies_job_id ON job_dependencies(job_id);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_depends_on_job_id ON job_dependencies(depends_on_job_id);

-- Queue lock query used by queue_controller.lock_pending_job:
--
-- SELECT *
-- FROM job_runs
-- WHERE status = 'pending'
-- ORDER BY created_at
-- FOR UPDATE SKIP LOCKED
-- LIMIT 1;
