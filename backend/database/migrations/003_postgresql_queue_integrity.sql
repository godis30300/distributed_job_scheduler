-- Migration 003: PostgreSQL queue integrity, observability views, and DB-side helpers.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_users_role'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT ck_users_role
            CHECK (role IN ('admin', 'developer', 'operator', 'viewer'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_runs_trigger_type'
    ) THEN
        ALTER TABLE job_runs
            ADD CONSTRAINT ck_job_runs_trigger_type
            CHECK (trigger_type IN ('schedule', 'manual', 'api', 'retry', 'dependency'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_dependencies_not_self'
    ) THEN
        ALTER TABLE job_dependencies
            ADD CONSTRAINT ck_job_dependencies_not_self
            CHECK (job_id <> depends_on_job_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_dependencies_required_status'
    ) THEN
        ALTER TABLE job_dependencies
            ADD CONSTRAINT ck_job_dependencies_required_status
            CHECK (required_status IN ('success', 'failed', 'timeout', 'canceled'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_jobs_due_schedule
    ON jobs(next_run_at)
    WHERE enabled = TRUE AND status IN ('enabled', 'active') AND next_run_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_job_runs_pending_queue
    ON job_runs(created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_job_runs_running_locks
    ON job_runs(locked_until)
    WHERE status = 'running' AND locked_until IS NOT NULL;

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
