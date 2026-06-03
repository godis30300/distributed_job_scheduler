-- Migration 002: align DB fields with API/UI integration contract.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);

ALTER TABLE job_runs
    ADD COLUMN IF NOT EXISTS triggered_by VARCHAR(80);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_jobs_action_type'
    ) THEN
        ALTER TABLE jobs DROP CONSTRAINT ck_jobs_action_type;
    END IF;
END $$;

ALTER TABLE jobs
    ADD CONSTRAINT ck_jobs_action_type
    CHECK (action_type IN ('api_call', 'shell', 'report', 'email', 'backup', 'fail-test', 'long-task'));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_jobs_status'
    ) THEN
        ALTER TABLE jobs DROP CONSTRAINT ck_jobs_status;
    END IF;
END $$;

ALTER TABLE jobs
    ADD CONSTRAINT ck_jobs_status
    CHECK (status IN ('enabled', 'active', 'paused', 'disabled', 'deleted'));

UPDATE jobs
SET status = 'enabled'
WHERE status = 'active';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_job_runs_status'
    ) THEN
        ALTER TABLE job_runs DROP CONSTRAINT ck_job_runs_status;
    END IF;
END $$;

ALTER TABLE job_runs
    ADD CONSTRAINT ck_job_runs_status
    CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled'));
