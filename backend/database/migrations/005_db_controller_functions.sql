-- Migration 005: PostgreSQL DB controller functions.
-- These functions provide DB-owned helpers for job creation, job_run creation,
-- queue locking, status updates, log writes/searches, and dependencies.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION db_create_job(
    p_user_id VARCHAR,
    p_name VARCHAR,
    p_task_type VARCHAR,
    p_script TEXT,
    p_description TEXT DEFAULT NULL,
    p_working_dir TEXT DEFAULT NULL,
    p_schedule_rule VARCHAR DEFAULT 'manual',
    p_timeout_seconds INTEGER DEFAULT 300,
    p_max_retry INTEGER DEFAULT 3,
    p_status VARCHAR DEFAULT 'enabled',
    p_action_payload JSONB DEFAULT NULL
)
RETURNS jobs AS $$
DECLARE
    inserted_job jobs;
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
        p_status IN ('enabled', 'active'),
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
    p_trigger_type VARCHAR DEFAULT 'manual',
    p_triggered_by VARCHAR DEFAULT NULL,
    p_retry_count INTEGER DEFAULT 0
)
RETURNS job_runs AS $$
DECLARE
    source_job jobs;
    inserted_run job_runs;
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
        'pending',
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
    p_stream VARCHAR DEFAULT 'system'
)
RETURNS job_logs AS $$
DECLARE
    inserted_log job_logs;
    normalized_level VARCHAR;
BEGIN
    normalized_level := lower(p_log_level);
    IF normalized_level = 'warn' THEN
        normalized_level := 'warning';
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
BEGIN
    SELECT jr.id INTO selected_run_id
    FROM job_runs jr
    JOIN jobs j ON j.id = jr.job_id
    WHERE jr.status = 'pending'
      AND j.enabled = TRUE
      AND j.status IN ('enabled', 'active')
    ORDER BY jr.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF selected_run_id IS NULL THEN
        RETURN NULL;
    END IF;

    UPDATE job_runs
    SET
        status = 'running',
        worker_id = p_worker_id,
        locked_by = p_worker_id,
        locked_until = now() + make_interval(secs => p_lock_seconds),
        start_time = COALESCE(start_time, now()),
        heartbeat_at = now()
    WHERE id = selected_run_id
    RETURNING * INTO locked_run;

    PERFORM db_save_job_log(locked_run.id, 'info', 'Locked by ' || p_worker_id, 'system');
    RETURN locked_run;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_update_job_run_status(
    p_run_id VARCHAR,
    p_status VARCHAR,
    p_stdout TEXT DEFAULT NULL,
    p_stderr TEXT DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS job_runs AS $$
DECLARE
    updated_run job_runs;
BEGIN
    IF p_status NOT IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled') THEN
        RAISE EXCEPTION 'invalid job run status: %', p_status;
    END IF;

    UPDATE job_runs
    SET
        status = p_status,
        start_time = CASE WHEN p_status = 'running' THEN COALESCE(start_time, now()) ELSE start_time END,
        end_time = CASE WHEN p_status IN ('success', 'failed', 'timeout', 'canceled') THEN now() ELSE end_time END,
        heartbeat_at = CASE WHEN p_status IN ('running', 'success', 'failed', 'timeout', 'canceled') THEN now() ELSE heartbeat_at END,
        locked_by = CASE WHEN p_status IN ('success', 'failed', 'timeout', 'canceled') THEN NULL ELSE locked_by END,
        locked_until = CASE WHEN p_status IN ('success', 'failed', 'timeout', 'canceled') THEN NULL ELSE locked_until END,
        stdout = COALESCE(p_stdout, stdout),
        stderr = COALESCE(p_stderr, stderr),
        error_message = COALESCE(p_error_message, error_message)
    WHERE id = p_run_id
    RETURNING * INTO updated_run;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'job run not found: %', p_run_id;
    END IF;

    IF p_stdout IS NOT NULL AND p_stdout <> '' THEN
        PERFORM db_save_job_log(p_run_id, 'info', p_stdout, 'stdout');
    END IF;
    IF p_stderr IS NOT NULL AND p_stderr <> '' THEN
        PERFORM db_save_job_log(p_run_id, 'error', p_stderr, 'stderr');
    END IF;
    IF p_error_message IS NOT NULL AND p_error_message <> '' THEN
        PERFORM db_save_job_log(p_run_id, 'error', p_error_message, 'system');
    END IF;
    IF p_status IN ('success', 'failed', 'timeout', 'canceled') THEN
        PERFORM db_save_job_log(p_run_id, CASE WHEN p_status = 'success' THEN 'info' ELSE 'error' END, 'Run finished: ' || p_status, 'system');
    END IF;

    SELECT * INTO updated_run FROM job_runs WHERE id = p_run_id;
    RETURN updated_run;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION db_create_dependency(
    p_job_id VARCHAR,
    p_depends_on_job_id VARCHAR,
    p_required_status VARCHAR DEFAULT 'success'
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
    latest_status VARCHAR;
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
        jr.status,
        jl.log_level,
        jl.stream,
        jl.message,
        jl.created_at
    FROM job_logs jl
    JOIN job_runs jr ON jr.id = jl.job_run_id
    JOIN jobs j ON j.id = jr.job_id
    WHERE (p_task_name IS NULL OR j.task_name = p_task_name)
      AND (p_status IS NULL OR jr.status = p_status)
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
    jr.status AS run_status,
    jr.trigger_type,
    jr.triggered_by,
    jr.worker_id,
    jr.start_time,
    jr.end_time,
    jr.duration_seconds,
    jr.duration_seconds_decimal,
    jr.duration_ms,
    jr.retry_count,
    jr.task_type,
    jr.script,
    jr.working_dir,
    jr.error_message,
    j.id AS job_id,
    j.name,
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
