-- Migration 007: Event Notifications
-- This enables event-driven triggering using PostgreSQL LISTEN/NOTIFY.

CREATE OR REPLACE FUNCTION fn_notify_job_run_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Only notify if the status becomes 'pending'
    IF (TG_OP = 'INSERT' AND NEW.status = 'pending') OR (TG_OP = 'UPDATE' AND OLD.status <> 'pending' AND NEW.status = 'pending') THEN
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
