-- Migration 003: make job_runs self-contained execution records.
-- This keeps queued/history runs stable even if the source job is edited later.

ALTER TABLE job_runs
    ADD COLUMN IF NOT EXISTS action_type VARCHAR(40),
    ADD COLUMN IF NOT EXISTS timeout_seconds INTEGER;

UPDATE job_runs AS jr
SET
    action_type = COALESCE(jr.action_type, j.action_type),
    action_payload = COALESCE(jr.action_payload, j.action_payload),
    timeout_seconds = COALESCE(jr.timeout_seconds, NULLIF(j.timeout_seconds, 0), 300)
FROM jobs AS j
WHERE jr.job_id = j.id;

UPDATE job_runs
SET timeout_seconds = 300
WHERE timeout_seconds IS NULL OR timeout_seconds <= 0;

ALTER TABLE job_runs
    ALTER COLUMN action_type SET NOT NULL,
    ALTER COLUMN timeout_seconds SET NOT NULL,
    ALTER COLUMN timeout_seconds SET DEFAULT 300;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_runs_action_type'
    ) THEN
        ALTER TABLE job_runs DROP CONSTRAINT ck_job_runs_action_type;
    END IF;
END $$;

ALTER TABLE job_runs
    ADD CONSTRAINT ck_job_runs_action_type
    CHECK (action_type IN ('api_call', 'shell', 'report', 'email', 'backup', 'fail-test', 'long-task'));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_runs_timeout_positive'
    ) THEN
        ALTER TABLE job_runs DROP CONSTRAINT ck_job_runs_timeout_positive;
    END IF;
END $$;

ALTER TABLE job_runs
    ADD CONSTRAINT ck_job_runs_timeout_positive
    CHECK (timeout_seconds > 0);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_dependencies_required_status'
    ) THEN
        ALTER TABLE job_dependencies DROP CONSTRAINT ck_job_dependencies_required_status;
    END IF;
END $$;

ALTER TABLE job_dependencies
    ADD CONSTRAINT ck_job_dependencies_required_status
    CHECK (required_status IN ('success', 'failed', 'timeout', 'canceled'));

CREATE INDEX IF NOT EXISTS idx_jobs_enabled_status_next_run_at ON jobs(enabled, status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_pending_queue ON job_runs(created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_job_runs_job_status_created_at ON job_runs(job_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_start_time ON job_runs(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_job_runs_start_time ON job_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_job_logs_created_at ON job_logs(created_at);

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
