-- Add metadata_json to job_runs
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS metadata_json JSONB;

-- Define domains if not exists to avoid duplication
DO $$ BEGIN
    CREATE DOMAIN job_action_type AS VARCHAR(40)
        CHECK (VALUE IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE DOMAIN job_run_status AS VARCHAR(32)
        CHECK (VALUE IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled', 'awaiting_result'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Update constraints for jobs to use the new DOMAINs or at least simplify
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_action_type;
ALTER TABLE jobs ALTER COLUMN action_type TYPE job_action_type;

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_task_type;
ALTER TABLE jobs ALTER COLUMN task_type TYPE job_action_type;

-- Update constraints for job_runs
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_status;
ALTER TABLE job_runs ALTER COLUMN status TYPE job_run_status;

ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_action_type;
ALTER TABLE job_runs ALTER COLUMN action_type TYPE job_action_type;

ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_task_type;
ALTER TABLE job_runs ALTER COLUMN task_type TYPE job_action_type;
