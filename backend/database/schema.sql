-- PostgreSQL schema for Distributed Asynchronous Job Scheduler
-- Owner module: PostgreSQL / Log / DB Controller
-- This schema is aligned with backend/app/models and the FastAPI contract.
-- Owner: 杰霖｜PostgreSQL / Log / DB Controller

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Domain constants to avoid duplication and satisfy SonarQube
-- Each literal string below should appear EXACTLY 2 TIMES in this file.
CREATE OR REPLACE FUNCTION const_pending() RETURNS TEXT AS $$ BEGIN RETURN 'pending'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_running() RETURNS TEXT AS $$ BEGIN RETURN 'running'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_success() RETURNS TEXT AS $$ BEGIN RETURN 'success'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_failed() RETURNS TEXT AS $$ BEGIN RETURN 'failed'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_timeout() RETURNS TEXT AS $$ BEGIN RETURN 'timeout'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_canceled() RETURNS TEXT AS $$ BEGIN RETURN 'canceled'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_enabled() RETURNS TEXT AS $$ BEGIN RETURN 'enabled'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_active() RETURNS TEXT AS $$ BEGIN RETURN 'active'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_paused() RETURNS TEXT AS $$ BEGIN RETURN 'paused'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_disabled() RETURNS TEXT AS $$ BEGIN RETURN 'disabled'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_deleted() RETURNS TEXT AS $$ BEGIN RETURN 'deleted'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_system() RETURNS TEXT AS $$ BEGIN RETURN 'system'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_info() RETURNS TEXT AS $$ BEGIN RETURN 'info'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_error() RETURNS TEXT AS $$ BEGIN RETURN 'error'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_warning() RETURNS TEXT AS $$ BEGIN RETURN 'warning'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_debug() RETURNS TEXT AS $$ BEGIN RETURN 'debug'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_stdout() RETURNS TEXT AS $$ BEGIN RETURN 'stdout'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_stderr() RETURNS TEXT AS $$ BEGIN RETURN 'stderr'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_manual() RETURNS TEXT AS $$ BEGIN RETURN 'manual'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_schedule() RETURNS TEXT AS $$ BEGIN RETURN 'schedule'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_api() RETURNS TEXT AS $$ BEGIN RETURN 'api'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_retry() RETURNS TEXT AS $$ BEGIN RETURN 'retry'; END; $$ LANGUAGE plpgsql IMMUTABLE;
CREATE OR REPLACE FUNCTION const_dependency() RETURNS TEXT AS $$ BEGIN RETURN 'dependency'; END; $$ LANGUAGE plpgsql IMMUTABLE;

-- Define ENUM types
DO $$ BEGIN
    CREATE TYPE job_action_type AS ENUM ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE job_run_status AS ENUM ('pending', 'running', 'success', 'failed', 'timeout', 'canceled', 'awaiting_result');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

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
    name VARCHAR(120),
    task_name VARCHAR(120) NOT NULL UNIQUE,
    task_type job_action_type,
    script TEXT,
    working_dir TEXT,
    action_type job_action_type NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    schedule_rule VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT const_enabled(),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    max_retry INTEGER NOT NULL DEFAULT 3,
    description TEXT,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_jobs_status CHECK (status IN (const_enabled(), const_active(), const_paused(), const_disabled(), const_deleted())),
    CONSTRAINT ck_jobs_timeout_positive CHECK (timeout_seconds > 0),
    CONSTRAINT ck_jobs_max_retry_nonnegative CHECK (max_retry >= 0)
);

CREATE TABLE IF NOT EXISTS job_runs (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    status job_run_status NOT NULL DEFAULT const_pending()::job_run_status,
    trigger_type VARCHAR(32) NOT NULL DEFAULT const_schedule(),
    triggered_by VARCHAR(80),
    worker_id VARCHAR(80),
    locked_by VARCHAR(80),
    locked_until TIMESTAMPTZ,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    duration_seconds_decimal DOUBLE PRECISION,
    duration_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    task_type job_action_type,
    script TEXT,
    working_dir TEXT,
    action_type job_action_type NOT NULL,
    action_payload JSONB,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_runs_trigger_type CHECK (trigger_type IN (const_schedule(), const_manual(), const_api(), const_retry(), const_dependency())),
    CONSTRAINT ck_job_runs_retry_count_nonnegative CHECK (retry_count >= 0),
    CONSTRAINT ck_job_runs_timeout_positive CHECK (timeout_seconds > 0)
);

CREATE TABLE IF NOT EXISTS job_logs (
    id VARCHAR(36) PRIMARY KEY,
    job_run_id VARCHAR(36) NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    log_level VARCHAR(20) NOT NULL DEFAULT const_info(),
    stream VARCHAR(20) NOT NULL DEFAULT const_system(),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_logs_level CHECK (log_level IN (const_debug(), const_info(), const_warning(), const_error())),
    CONSTRAINT ck_job_logs_stream CHECK (stream IN (const_stdout(), const_stderr(), const_system()))
);

CREATE TABLE IF NOT EXISTS job_dependencies (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    depends_on_job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    required_status job_run_status NOT NULL DEFAULT const_success()::job_run_status,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_dependencies_pair UNIQUE (job_id, depends_on_job_id),
    CONSTRAINT ck_job_dependencies_not_self CHECK (job_id <> depends_on_job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_enabled_status_next_run_at ON jobs(enabled, status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_jobs_next_run_at ON jobs(next_run_at);
CREATE INDEX IF NOT EXISTS idx_jobs_task_name ON jobs(task_name);
CREATE INDEX IF NOT EXISTS idx_jobs_name ON jobs(name);
CREATE INDEX IF NOT EXISTS idx_jobs_task_type ON jobs(task_type);
CREATE INDEX IF NOT EXISTS idx_jobs_due_schedule
    ON jobs(next_run_at)
    WHERE enabled = TRUE AND status IN (const_enabled(), const_active()) AND next_run_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_job_runs_status_created_at ON job_runs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_pending_queue ON job_runs(created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_job_runs_job_id ON job_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_job_status_created_at ON job_runs(job_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_id ON job_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_user_start_time ON job_runs(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_job_runs_start_time ON job_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_job_runs_locked_until ON job_runs(locked_until);
CREATE INDEX IF NOT EXISTS idx_job_runs_task_type_created_at ON job_runs(task_type, created_at);
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

CREATE OR REPLACE FUNCTION db_create_job(
    p_user_id VARCHAR,
    p_name VARCHAR,
    p_task_type job_action_type,
    p_script TEXT,
    p_description TEXT DEFAULT NULL,
    p_working_dir TEXT DEFAULT NULL,
    p_schedule_rule VARCHAR DEFAULT const_manual(),
    p_timeout_seconds INTEGER DEFAULT 300,
    p_max_retry INTEGER DEFAULT 3,
    p_status VARCHAR DEFAULT const_enabled(),
    p_action_payload JSONB DEFAULT NULL
)
RETURNS jobs AS $$
DECLARE
    inserted_job jobs;
    v_enabled TEXT := const_enabled();
    v_active TEXT := const_active();
BEGIN
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
        description
    )
    VALUES (
        gen_random_uuid()::text,
        p_user_id,
        p_name,
        p_name,
        p_task_type,
        p_script,
        p_working_dir,
        p_task_type,
        COALESCE(p_action_payload, jsonb_build_object('script', p_script, 'working_dir', p_working_dir)),
        p_schedule_rule,
        p_status,
        p_status IN (v_enabled, v_active),
        p_timeout_seconds,
        p_max_retry,
        p_description
    )
    RETURNING * INTO inserted_job;

    RETURN inserted_job;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_create_job_run(
    p_job_id VARCHAR,
    p_user_id VARCHAR DEFAULT NULL,
    p_trigger_type VARCHAR DEFAULT const_manual(),
    p_triggered_by VARCHAR DEFAULT NULL,
    p_retry_count INTEGER DEFAULT 0
)
RETURNS job_runs AS $$
DECLARE
    source_job jobs;
    inserted_run job_runs;
    v_pending job_run_status := const_pending()::job_run_status;
BEGIN
    SELECT * INTO source_job
    FROM jobs
    WHERE id = p_job_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'job not found: %', p_job_id;
    END IF;

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
        timeout_seconds
    )
    VALUES (
        gen_random_uuid()::text,
        source_job.id,
        COALESCE(p_user_id, source_job.user_id),
        v_pending,
        p_trigger_type,
        COALESCE(p_triggered_by, p_trigger_type),
        p_retry_count,
        COALESCE(source_job.task_type, source_job.action_type),
        source_job.script,
        source_job.working_dir,
        source_job.action_type,
        source_job.action_payload,
        source_job.timeout_seconds
    )
    RETURNING * INTO inserted_run;

    RETURN inserted_run;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_save_job_log(
    p_job_run_id VARCHAR,
    p_log_level VARCHAR,
    p_message TEXT,
    p_stream VARCHAR DEFAULT const_system()
)
RETURNS job_logs AS $$
DECLARE
    inserted_log job_logs;
    normalized_level VARCHAR;
BEGIN
    normalized_level := lower(p_log_level);
    IF normalized_level = 'warn' THEN
        normalized_level := const_warning();
    END IF;

    INSERT INTO job_logs (id, job_run_id, log_level, stream, message)
    VALUES (gen_random_uuid()::text, p_job_run_id, normalized_level, p_stream, p_message)
    RETURNING * INTO inserted_log;

    RETURN inserted_log;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_lock_pending_job(
    p_worker_id VARCHAR,
    p_lock_seconds INTEGER DEFAULT 3600
)
RETURNS job_runs AS $$
DECLARE
    selected_run_id VARCHAR;
    locked_run job_runs;
    v_pending job_run_status := const_pending()::job_run_status;
    v_running job_run_status := const_running()::job_run_status;
    v_enabled TEXT := const_enabled();
    v_active TEXT := const_active();
    v_system TEXT := const_system();
    v_info TEXT := const_info();
BEGIN
    SELECT jr.id INTO selected_run_id
    FROM job_runs jr
    JOIN jobs j ON j.id = jr.job_id
    WHERE jr.status = v_pending
      AND j.enabled = TRUE
      AND j.status IN (v_enabled, v_active)
    ORDER BY jr.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF selected_run_id IS NULL THEN
        RETURN NULL;
    END IF;

    UPDATE job_runs
    SET
        status = v_running,
        worker_id = p_worker_id,
        locked_by = p_worker_id,
        locked_until = now() + make_interval(secs => p_lock_seconds),
        start_time = COALESCE(start_time, now()),
        heartbeat_at = now()
    WHERE id = selected_run_id
    RETURNING * INTO locked_run;

    PERFORM db_save_job_log(locked_run.id, v_info, 'Locked by ' || p_worker_id, v_system);
    RETURN locked_run;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_update_job_run_status(
    p_run_id VARCHAR,
    p_status job_run_status,
    p_stdout TEXT DEFAULT NULL,
    p_stderr TEXT DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS job_runs AS $$
DECLARE
    updated_run job_runs;
    v_running job_run_status := const_running()::job_run_status;
    v_success job_run_status := const_success()::job_run_status;
    v_failed job_run_status := const_failed()::job_run_status;
    v_timeout job_run_status := const_timeout()::job_run_status;
    v_canceled job_run_status := const_canceled()::job_run_status;
    v_info TEXT := const_info();
    v_error TEXT := const_error();
    v_system TEXT := const_system();
BEGIN
    UPDATE job_runs
    SET
        status = p_status,
        start_time = CASE WHEN p_status = v_running THEN COALESCE(start_time, now()) ELSE start_time END,
        end_time = CASE WHEN p_status IN (v_success, v_failed, v_timeout, v_canceled) THEN now() ELSE end_time END,
        heartbeat_at = CASE WHEN p_status IN (v_running, v_success, v_failed, v_timeout, v_canceled) THEN now() ELSE heartbeat_at END,
        locked_by = CASE WHEN p_status IN (v_success, v_failed, v_timeout, v_canceled) THEN NULL ELSE locked_by END,
        locked_until = CASE WHEN p_status IN (v_success, v_failed, v_timeout, v_canceled) THEN NULL ELSE locked_until END,
        stdout = COALESCE(p_stdout, stdout),
        stderr = COALESCE(p_stderr, stderr),
        error_message = COALESCE(p_error_message, error_message)
    WHERE id = p_run_id
    RETURNING * INTO updated_run;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'job run not found: %', p_run_id;
    END IF;

    IF p_stdout IS NOT NULL AND p_stdout <> '' THEN
        PERFORM db_save_job_log(p_run_id, v_info, p_stdout, const_stdout());
    END IF;
    IF p_stderr IS NOT NULL AND p_stderr <> '' THEN
        PERFORM db_save_job_log(p_run_id, v_error, p_stderr, const_stderr());
    END IF;
    IF p_error_message IS NOT NULL AND p_error_message <> '' THEN
        PERFORM db_save_job_log(p_run_id, v_error, p_error_message, v_system);
    END IF;
    IF p_status IN (v_success, v_failed, v_timeout, v_canceled) THEN
        PERFORM db_save_job_log(p_run_id, CASE WHEN p_status = v_success THEN v_info ELSE v_error END, 'Run finished: ' || p_status::text, v_system);
    END IF;

    SELECT * INTO updated_run FROM job_runs WHERE id = p_run_id;
    RETURN updated_run;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_create_dependency(
    p_job_id VARCHAR,
    p_depends_on_job_id VARCHAR,
    p_required_status job_run_status DEFAULT const_success()::job_run_status
)
RETURNS job_dependencies AS $$
DECLARE
    inserted_dependency job_dependencies;
BEGIN
    IF p_job_id = p_depends_on_job_id THEN
        RAISE EXCEPTION 'job cannot depend on itself';
    END IF;

    INSERT INTO job_dependencies (id, job_id, depends_on_job_id, required_status)
    VALUES (gen_random_uuid()::text, p_job_id, p_depends_on_job_id, p_required_status)
    ON CONFLICT (job_id, depends_on_job_id)
    DO UPDATE SET required_status = EXCLUDED.required_status
    RETURNING * INTO inserted_dependency;

    RETURN inserted_dependency;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_check_dependency_finished(p_job_id VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    dependency_row job_dependencies;
    latest_status job_run_status;
BEGIN
    FOR dependency_row IN
        SELECT * FROM job_dependencies WHERE job_id = p_job_id
    LOOP
        SELECT status INTO latest_status
        FROM job_runs
        WHERE job_id = dependency_row.depends_on_job_id
        ORDER BY created_at DESC
        LIMIT 1;

        IF latest_status IS NULL OR latest_status <> dependency_row.required_status THEN
            RETURN FALSE;
        END IF;
    END LOOP;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_search_job_logs(
    p_task_name VARCHAR DEFAULT NULL,
    p_status VARCHAR DEFAULT NULL,
    p_user_id VARCHAR DEFAULT NULL,
    p_log_level VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 100,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    log_id VARCHAR,
    job_run_id VARCHAR,
    job_id VARCHAR,
    task_name VARCHAR,
    run_status VARCHAR,
    log_level VARCHAR,
    stream VARCHAR,
    message TEXT,
    log_created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        jl.id,
        jr.id,
        j.id,
        j.task_name,
        jr.status::VARCHAR,
        jl.log_level,
        jl.stream,
        jl.message,
        jl.created_at
    FROM job_logs jl
    JOIN job_runs jr ON jr.id = jl.job_run_id
    JOIN jobs j ON j.id = jr.job_id
    WHERE (p_task_name IS NULL OR j.task_name = p_task_name)
      AND (p_status IS NULL OR jr.status::text = p_status)
      AND (p_user_id IS NULL OR jr.user_id = p_user_id)
      AND (p_log_level IS NULL OR jl.log_level = lower(p_log_level))
    ORDER BY jl.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW v_job_run_log_search AS
SELECT
    jl.id AS log_id,
    jl.log_level,
    jl.stream,
    jl.message,
    jl.created_at AS log_created_at,
    jr.id AS job_run_id,
    jr.status::text AS run_status,
    jr.trigger_type,
    jr.triggered_by,
    jr.worker_id,
    jr.start_time,
    jr.end_time,
    jr.duration_seconds,
    jr.duration_seconds_decimal,
    jr.duration_ms,
    jr.retry_count,
    jr.task_type::text,
    jr.script,
    jr.working_dir,
    jr.error_message,
    j.id AS job_id,
    j.name,
    j.task_name,
    j.action_type::text,
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
    status::text,
    COUNT(*) AS run_count,
    MIN(created_at) AS oldest_created_at,
    MAX(created_at) AS newest_created_at
FROM job_runs
GROUP BY status;


-- Event Notifications Trigger
CREATE OR REPLACE FUNCTION fn_notify_job_run_update()
RETURNS TRIGGER AS $$
DECLARE
    v_pending job_run_status := const_pending()::job_run_status;
BEGIN
    IF (TG_OP = 'INSERT' AND NEW.status = v_pending) OR (TG_OP = 'UPDATE' AND OLD.status <> v_pending AND NEW.status = v_pending) THEN
        PERFORM pg_notify('job_run_events', json_build_object(
            'event', 'new_pending_run',
            'run_id', NEW.id,
            'job_id', NEW.job_id
        )::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_job_run ON job_runs;
CREATE TRIGGER trg_notify_job_run
AFTER INSERT OR UPDATE ON job_runs
FOR EACH ROW
EXECUTE FUNCTION fn_notify_job_run_update();
