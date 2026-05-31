-- PostgreSQL schema for Distributed Asynchronous Job Scheduler
-- Owner module: PostgreSQL / Log / DB Controller
-- This schema is aligned with backend/app/models and the FastAPI contract.
-- Owner: 杰霖｜PostgreSQL / Log / DB Controller

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'developer', 'operator', 'viewer'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    task_name VARCHAR(120) NOT NULL UNIQUE,
    action_type VARCHAR(40) NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    schedule_rule VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'enabled',
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
    action_type VARCHAR(40) NOT NULL,
    action_payload JSONB,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_runs_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled')),
    CONSTRAINT ck_job_runs_trigger_type CHECK (trigger_type IN ('schedule', 'manual', 'api', 'retry', 'dependency')),
    CONSTRAINT ck_job_runs_retry_count_nonnegative CHECK (retry_count >= 0),
    CONSTRAINT ck_job_runs_action_type CHECK (action_type IN ('api_call', 'shell', 'report', 'email', 'backup', 'fail-test', 'long-task')),
    CONSTRAINT ck_job_runs_timeout_positive CHECK (timeout_seconds > 0)
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
    CONSTRAINT ck_job_dependencies_not_self CHECK (job_id <> depends_on_job_id),
    CONSTRAINT ck_job_dependencies_required_status CHECK (required_status IN ('success', 'failed', 'timeout', 'canceled'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_enabled_status_next_run_at ON jobs(enabled, status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_jobs_next_run_at ON jobs(next_run_at);
CREATE INDEX IF NOT EXISTS idx_jobs_task_name ON jobs(task_name);
CREATE INDEX IF NOT EXISTS idx_jobs_due_schedule
    ON jobs(next_run_at)
    WHERE enabled = TRUE AND status IN ('enabled', 'active') AND next_run_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_job_runs_status_created_at ON job_runs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_pending_queue ON job_runs(created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_job_runs_job_id ON job_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_job_status_created_at ON job_runs(job_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_id ON job_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_start_time ON job_runs(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_job_runs_start_time ON job_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_job_runs_locked_until ON job_runs(locked_until);
CREATE INDEX IF NOT EXISTS idx_job_runs_running_locks
    ON job_runs(locked_until)
    WHERE status = 'running' AND locked_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_job_logs_run_created_at ON job_logs(job_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_logs_level_created_at ON job_logs(log_level, created_at);
CREATE INDEX IF NOT EXISTS idx_job_logs_created_at ON job_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_job_dependencies_job_id ON job_dependencies(job_id);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_depends_on_job_id ON job_dependencies(depends_on_job_id);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON jobs;
CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_job_runs_updated_at ON job_runs;
CREATE TRIGGER trg_job_runs_updated_at
BEFORE UPDATE ON job_runs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION set_job_run_duration_seconds()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.start_time IS NOT NULL AND NEW.end_time IS NOT NULL THEN
        NEW.duration_seconds = GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)))::INTEGER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_runs_duration_seconds ON job_runs;
CREATE TRIGGER trg_job_runs_duration_seconds
BEFORE INSERT OR UPDATE OF start_time, end_time ON job_runs
FOR EACH ROW
EXECUTE FUNCTION set_job_run_duration_seconds();

CREATE OR REPLACE VIEW v_job_run_log_search AS
SELECT
    jl.id AS log_id,
    jl.log_level,
    jl.stream,
    jl.message,
    jl.created_at AS log_created_at,
    jr.id AS job_run_id,
    jr.status AS run_status,
    jr.trigger_type,
    jr.triggered_by,
    jr.worker_id,
    jr.start_time,
    jr.end_time,
    jr.duration_seconds,
    jr.retry_count,
    jr.error_message,
    j.id AS job_id,
    j.task_name,
    j.action_type,
    j.schedule_rule,
    u.id AS user_id,
    u.username,
    u.email
FROM job_logs jl
JOIN job_runs jr ON jr.id = jl.job_run_id
JOIN jobs j ON j.id = jr.job_id
LEFT JOIN users u ON u.id = jr.user_id;

CREATE OR REPLACE VIEW v_job_queue_status AS
SELECT
    status,
    COUNT(*) AS run_count,
    MIN(created_at) AS oldest_created_at,
    MAX(created_at) AS newest_created_at
FROM job_runs
GROUP BY status;
