-- Migration 004: task script fields and non-zero duration tracking.
-- Adds the user-facing task contract:
--   id, name, task_type, script, description, working_dir
-- and keeps old task_name/action_type/action_payload fields compatible.

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS name VARCHAR(120),
ADD COLUMN IF NOT EXISTS task_type VARCHAR(40),
ADD COLUMN IF NOT EXISTS script TEXT,
ADD COLUMN IF NOT EXISTS working_dir TEXT;

UPDATE jobs
SET
    name = COALESCE(name, task_name),
    task_type = COALESCE(task_type, action_type),
    script = COALESCE(script, action_payload ->> 'script'),
    working_dir = COALESCE(working_dir, action_payload ->> 'working_dir');

ALTER TABLE job_runs
ADD COLUMN IF NOT EXISTS duration_ms INTEGER,
ADD COLUMN IF NOT EXISTS duration_seconds_decimal DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS task_type VARCHAR(40),
ADD COLUMN IF NOT EXISTS script TEXT,
ADD COLUMN IF NOT EXISTS working_dir TEXT;

UPDATE job_runs
SET
    task_type = COALESCE(task_type, action_type),
    script = COALESCE(script, action_payload ->> 'script'),
    working_dir = COALESCE(working_dir, action_payload ->> 'working_dir'),
    duration_ms = CASE
        WHEN start_time IS NOT NULL AND end_time IS NOT NULL
        THEN GREATEST(1, CEIL(EXTRACT(EPOCH FROM (end_time - start_time)) * 1000)::INTEGER)
        ELSE duration_ms
    END,
    duration_seconds_decimal = CASE
        WHEN start_time IS NOT NULL AND end_time IS NOT NULL
        THEN ROUND((GREATEST(1, CEIL(EXTRACT(EPOCH FROM (end_time - start_time)) * 1000)::INTEGER) / 1000.0)::numeric, 3)::DOUBLE PRECISION
        ELSE duration_seconds_decimal
    END,
    duration_seconds = CASE
        WHEN start_time IS NOT NULL AND end_time IS NOT NULL
        THEN GREATEST(1, CEIL(EXTRACT(EPOCH FROM (end_time - start_time)))::INTEGER)
        ELSE duration_seconds
    END;

ALTER TABLE jobs
DROP CONSTRAINT IF EXISTS ck_jobs_action_type,
DROP CONSTRAINT IF EXISTS ck_jobs_task_type;

ALTER TABLE jobs
ADD CONSTRAINT ck_jobs_action_type CHECK (action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task')),
ADD CONSTRAINT ck_jobs_task_type CHECK (task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task'));

ALTER TABLE job_runs
DROP CONSTRAINT IF EXISTS ck_job_runs_action_type,
DROP CONSTRAINT IF EXISTS ck_job_runs_task_type;

ALTER TABLE job_runs
ADD CONSTRAINT ck_job_runs_action_type CHECK (action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task')),
ADD CONSTRAINT ck_job_runs_task_type CHECK (task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task'));

CREATE INDEX IF NOT EXISTS idx_jobs_name ON jobs(name);
CREATE INDEX IF NOT EXISTS idx_jobs_task_type ON jobs(task_type);
CREATE INDEX IF NOT EXISTS idx_job_runs_task_type_created_at ON job_runs(task_type, created_at);

CREATE OR REPLACE FUNCTION set_job_run_duration_seconds()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.start_time IS NOT NULL AND NEW.end_time IS NOT NULL THEN
        NEW.duration_ms = GREATEST(1, CEIL(EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)) * 1000)::INTEGER);
        NEW.duration_seconds_decimal = ROUND((NEW.duration_ms / 1000.0)::numeric, 3)::DOUBLE PRECISION;
        NEW.duration_seconds = GREATEST(1, CEIL(EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)))::INTEGER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_runs_duration_seconds ON job_runs;
CREATE TRIGGER trg_job_runs_duration_seconds
BEFORE INSERT OR UPDATE OF start_time, end_time ON job_runs
FOR EACH ROW
EXECUTE FUNCTION set_job_run_duration_seconds();
