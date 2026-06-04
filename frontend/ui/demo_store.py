from datetime import datetime, timezone
from uuid import uuid4


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ensure_demo_data(request):
    request.session.setdefault('demo_users', {})
    if 'demo_jobs' not in request.session:
        job_id = str(uuid4())
        request.session['demo_jobs'] = [
            {
                'id': job_id,
                'task_name': 'Daily Report Demo',
                'status': 'enabled',
                'user': 'demo',
                'schedule_type': 'cron',
                'cron_expression': '0 2 * * *',
                'interval_seconds': '',
                'action': 'report',
                'timeout_seconds': 300,
                'retry_limit': 3,
                'created_at': now_iso(),
                'updated_at': now_iso(),
            }
        ]
        request.session['demo_runs'] = [
            {
                'id': str(uuid4()),
                'job_id': job_id,
                'task_name': 'Daily Report Demo',
                'status': 'success',
                'user': 'demo',
                'start_time': now_iso(),
                'duration': 2.4,
                'action': 'report',
                'triggered_by': 'manual',
                'retry_count': 0,
            }
        ]
        request.session['demo_logs'] = {}
        first_run_id = request.session['demo_runs'][0]['id']
        request.session['demo_logs'][first_run_id] = [
            {'log_level': 'info', 'message': 'Start generating daily report', 'created_at': now_iso()},
            {'log_level': 'info', 'message': 'Report generated successfully', 'created_at': now_iso()},
        ]
        request.session.modified = True


def demo_login(request, username):
    request.session['token'] = f"demo-{uuid4()}"
    request.session['username'] = username
    ensure_demo_data(request)


def list_jobs(request):
    ensure_demo_data(request)
    return request.session['demo_jobs']


def get_job(request, job_id):
    for job in list_jobs(request):
        if str(job['id']) == str(job_id):
            return job
    return None


def create_job(request, data):
    ensure_demo_data(request)
    job = {
        'id': str(uuid4()),
        'task_name': data.get('task_name', ''),
        'status': data.get('status', 'enabled'),
        'user': request.session.get('username', 'demo'),
        'schedule_type': data.get('schedule_type', 'manual'),
        'cron_expression': data.get('cron_expression', ''),
        'interval_seconds': data.get('interval_seconds', ''),
        'action': data.get('action', 'report'),
        'timeout_seconds': int(data.get('timeout_seconds') or 300),
        'retry_limit': int(data.get('retry_limit') or 3),
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }
    request.session['demo_jobs'].append(job)
    request.session.modified = True
    return job


def update_job(request, job_id, data):
    ensure_demo_data(request)
    for job in request.session['demo_jobs']:
        if str(job['id']) == str(job_id):
            for key in ['task_name', 'status', 'schedule_type', 'cron_expression', 'interval_seconds', 'action', 'timeout_seconds', 'retry_limit']:
                if key in data:
                    job[key] = data[key]
            job['updated_at'] = now_iso()
            request.session.modified = True
            return job
    return None


def delete_job(request, job_id):
    ensure_demo_data(request)
    request.session['demo_jobs'] = [job for job in request.session['demo_jobs'] if str(job['id']) != str(job_id)]
    request.session.modified = True


def run_job(request, job_id, triggered_by='manual'):
    job = get_job(request, job_id)
    if not job:
        return None
    status = 'failed' if job.get('action') == 'fail-test' else 'success'
    run = {
        'id': str(uuid4()),
        'job_id': job['id'],
        'task_name': job['task_name'],
        'status': status,
        'user': request.session.get('username', 'demo'),
        'start_time': now_iso(),
        'duration': 1.2 if status == 'success' else 0.7,
        'action': job.get('action'),
        'triggered_by': triggered_by,
        'retry_count': 0 if triggered_by != 'retry' else 1,
    }
    request.session['demo_runs'].insert(0, run)
    request.session['demo_logs'][run['id']] = [
        {'log_level': 'info', 'message': f"Start action: {job.get('action')}", 'created_at': now_iso()},
        {'log_level': 'error' if status == 'failed' else 'info', 'message': 'Task failed by demo container' if status == 'failed' else 'Task finished successfully', 'created_at': now_iso()},
    ]
    request.session.modified = True
    return run


def list_runs(request):
    ensure_demo_data(request)
    return request.session['demo_runs']


def get_logs(request, run_id):
    ensure_demo_data(request)
    return request.session['demo_logs'].get(str(run_id), [])


def retry_run(request, run_id):
    ensure_demo_data(request)
    for run in request.session['demo_runs']:
        if str(run['id']) == str(run_id):
            return run_job(request, run['job_id'], triggered_by='retry')
    return None
