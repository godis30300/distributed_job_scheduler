-- Add metadata_json to job_runs
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS metadata_json JSONB;

-- Update constraints for jobs
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_action_type;
ALTER TABLE jobs ADD CONSTRAINT ck_jobs_action_type 
    CHECK (action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll'));

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_task_type;
ALTER TABLE jobs ADD CONSTRAINT ck_jobs_task_type 
    CHECK (task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll'));

-- Update constraints for job_runs
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_status;
ALTER TABLE job_runs ADD CONSTRAINT ck_job_runs_status 
    CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled', 'awaiting_result'));

ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_action_type;
ALTER TABLE job_runs ADD CONSTRAINT ck_job_runs_action_type 
    CHECK (action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll'));

ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS ck_job_runs_task_type;
ALTER TABLE job_runs ADD CONSTRAINT ck_job_runs_task_type 
    CHECK (task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll'));
