from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .api_client import BackendAPIClient, BackendAPIError
from .forms import JobForm, LoginForm, RegisterForm
from . import demo_store


def _is_logged_in(request):
    return bool(request.session.get('token'))


def _require_login(request):
    if not _is_logged_in(request):
        messages.warning(request, '請先登入。')
        return redirect('login')
    return None


def _client(request):
    return BackendAPIClient(token=request.session.get('token'))


def _extract_token(login_response):
    if not isinstance(login_response, dict):
        return None
    return login_response.get('access_token') or login_response.get('token') or login_response.get('jwt')


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            if settings.DEMO_MODE:
                demo_store.demo_login(request, username)
                messages.success(request, 'Demo 模式登入成功。')
                return redirect('dashboard')
            try:
                result = BackendAPIClient().login({'username': username, 'password': password})
                token = _extract_token(result)
                if not token:
                    raise BackendAPIError('登入成功但後端未回傳 access_token/token。')
                request.session['token'] = token
                request.session['username'] = username
                messages.success(request, '登入成功。')
                return redirect('dashboard')
            except BackendAPIError:
                messages.error(request, '帳號或密碼錯誤。')
    else:
        form = LoginForm()
    return render(request, 'ui/login.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            payload = form.cleaned_data
            if settings.DEMO_MODE:
                request.session.setdefault('demo_users', {})
                request.session['demo_users'][payload['username']] = payload
                request.session.modified = True
                messages.success(request, 'Demo 模式註冊成功，請登入。')
                return redirect('login')
            try:
                BackendAPIClient().register(payload)
                messages.success(request, '註冊成功，請登入。')
                return redirect('login')
            except BackendAPIError as exc:
                messages.error(request, f'註冊失敗：{exc}')
    else:
        form = RegisterForm()
    return render(request, 'ui/register.html', {'form': form})


def logout_view(request):
    request.session.flush()
    messages.success(request, '已登出。')
    return redirect('login')


def dashboard_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response

    try:
        jobs = demo_store.list_jobs(request) if settings.DEMO_MODE else _client(request).list_jobs()
        runs = demo_store.list_runs(request) if settings.DEMO_MODE else _client(request).list_job_runs()
        jobs = jobs if isinstance(jobs, list) else jobs.get('items', [])
        runs = runs if isinstance(runs, list) else runs.get('items', [])
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        jobs, runs = [], []

    stats = {
        'total_jobs': len(jobs),
        'enabled_jobs': len([j for j in jobs if j.get('status') == 'enabled']),
        'success_runs': len([r for r in runs if r.get('status') == 'success']),
        'failed_runs': len([r for r in runs if r.get('status') in ['failed', 'timeout']]),
        'running_runs': len([r for r in runs if r.get('status') == 'running']),
    }
    return render(request, 'ui/dashboard.html', {'stats': stats, 'jobs': jobs[:5], 'runs': runs[:5]})


def job_list_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        jobs = demo_store.list_jobs(request) if settings.DEMO_MODE else _client(request).list_jobs()
        jobs = jobs if isinstance(jobs, list) else jobs.get('items', [])
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        jobs = []
    return render(request, 'ui/job_list.html', {'jobs': jobs})


def job_list_partial_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        from django.http import HttpResponse
        return HttpResponse('')
    try:
        jobs = demo_store.list_jobs(request) if settings.DEMO_MODE else _client(request).list_jobs()
        jobs = jobs if isinstance(jobs, list) else jobs.get('items', [])
    except BackendAPIError:
        jobs = []
    return render(request, 'ui/partials/job_table.html', {'jobs': jobs})


def _prepare_job_payload(data):
    depends_on = [] if data.get('clear_dependencies') else data.get('depends_on', [])
    payload = {
        "task_name": data['task_name'],
        "description": data.get('description'),
        "status": data['status'],
        "action": data['action'],
        "api_method": data.get('api_method'),
        "api_url": data.get('api_url'),
        "working_dir": data.get('working_dir'),
        "shell_script": data.get('shell_script'),
        "script_content": data.get('script_content'),
        "schedule_type": data['schedule_type'],
        "cron_expression": data.get('cron_expression'),
        "interval_seconds": data.get('interval_seconds'),
        "timeout_seconds": data['timeout_seconds'],
        "retry_limit": data['retry_limit'],
        "depends_on": depends_on
    }
    return payload


def _prepare_initial_data(job):
    initial = {
        'task_name': job.get('task_name'),
        'description': job.get('description'),
        'status': job.get('status'),
        'timeout_seconds': job.get('timeout_seconds'),
        'retry_limit': job.get('retry_limit'),
        'schedule_type': job.get('schedule_type'),
        'cron_expression': job.get('cron_expression'),
        'interval_seconds': job.get('interval_seconds'),
        'action': job.get('action'),
        'clear_dependencies': False,
        'depends_on': job.get('depends_on', []),
    }
    
    # Action Payload extraction for flat fields in form
    payload = job.get('action_payload', {})
    atype = initial['action']
    if atype == 'api_call':
        initial['api_method'] = payload.get('method')
        initial['api_url'] = payload.get('url')
    elif atype in ['shell', 'python', 'python_script']:
        initial['shell_script'] = payload.get('script')
        initial['script_content'] = payload.get('content')
        initial['working_dir'] = payload.get('working_dir')
        
    return initial


@require_http_methods(['GET', 'POST'])
def job_create_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    
    try:
        all_jobs = demo_store.list_jobs(request) if settings.DEMO_MODE else _client(request).list_jobs()
        all_jobs = all_jobs if isinstance(all_jobs, list) else all_jobs.get('items', [])
        job_choices = [(j['task_name'], j['task_name']) for j in all_jobs]
    except BackendAPIError:
        job_choices = []

    if request.method == 'POST':
        form = JobForm(request.POST)
        form.fields['depends_on'].choices = job_choices
        if form.is_valid():
            payload = _prepare_job_payload(form.cleaned_data)
            if settings.DEMO_MODE:
                demo_store.create_job(request, payload)
            else:
                try:
                    _client(request).create_job(payload)
                except BackendAPIError as exc:
                    messages.error(request, str(exc))
                    return render(request, 'ui/job_form.html', {'form': form, 'mode': 'create'})
            messages.success(request, 'Job 建立成功。')
            return redirect('job_list')
    else:
        form = JobForm(initial={'status': 'enabled', 'schedule_type': 'manual', 'action': 'api_call'})
        form.fields['depends_on'].choices = job_choices
    return render(request, 'ui/job_form.html', {'form': form, 'mode': 'create'})


def job_detail_view(request, job_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        job = demo_store.get_job(request, job_id) if settings.DEMO_MODE else _client(request).get_job(job_id)
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        return redirect('job_list')
    if not job:
        messages.error(request, '找不到指定 Job。')
        return redirect('job_list')
    return render(request, 'ui/job_detail.html', {'job': job})


@require_http_methods(['GET', 'POST'])
def job_edit_view(request, job_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        job = demo_store.get_job(request, job_id) if settings.DEMO_MODE else _client(request).get_job(job_id)
        all_jobs = demo_store.list_jobs(request) if settings.DEMO_MODE else _client(request).list_jobs()
        all_jobs = all_jobs if isinstance(all_jobs, list) else all_jobs.get('items', [])
        # Exclude self from choices
        job_choices = [(j['task_name'], j['task_name']) for j in all_jobs if j['id'] != job_id]
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        return redirect('job_list')
    if not job:
        messages.error(request, '找不到指定 Job。')
        return redirect('job_list')

    if request.method == 'POST':
        form = JobForm(request.POST)
        form.fields['depends_on'].choices = job_choices
        if form.is_valid():
            payload = _prepare_job_payload(form.cleaned_data)
            if settings.DEMO_MODE:
                demo_store.update_job(request, job_id, payload)
            else:
                try:
                    _client(request).update_job(job_id, payload)
                except BackendAPIError as exc:
                    messages.error(request, str(exc))
                    return render(request, 'ui/job_form.html', {'form': form, 'mode': 'edit', 'job': job})
            messages.success(request, 'Job 更新成功。')
            return redirect('job_detail', job_id=job_id)
    else:
        form = JobForm(initial=_prepare_initial_data(job))
        form.fields['depends_on'].choices = job_choices
    return render(request, 'ui/job_form.html', {'form': form, 'mode': 'edit', 'job': job})


@require_POST
def job_delete_view(request, job_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        if settings.DEMO_MODE:
            demo_store.delete_job(request, job_id)
        else:
            _client(request).delete_job(job_id)
        messages.success(request, 'Job 已刪除。')
    except BackendAPIError as exc:
        messages.error(request, str(exc))
    return redirect('job_list')


@require_POST
def job_run_view(request, job_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        if settings.DEMO_MODE:
            demo_store.run_job(request, job_id)
        else:
            _client(request).run_job(job_id)
        messages.success(request, '已觸發 Job。')
    except BackendAPIError as exc:
        messages.error(request, str(exc))
    return redirect('job_runs')


def job_runs_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        runs = demo_store.list_runs(request) if settings.DEMO_MODE else _client(request).list_job_runs()
        runs = runs if isinstance(runs, list) else runs.get('items', [])
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        runs = []
    return render(request, 'ui/job_runs.html', {'runs': runs})


def job_runs_partial_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        from django.http import HttpResponse
        return HttpResponse('')
    try:
        runs = demo_store.list_runs(request) if settings.DEMO_MODE else _client(request).list_job_runs()
        runs = runs if isinstance(runs, list) else runs.get('items', [])
    except BackendAPIError:
        runs = []
    return render(request, 'ui/partials/run_table.html', {'runs': runs})


@require_POST
def job_runs_clear_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        if not settings.DEMO_MODE:
            _client(request).clear_all_runs()
        messages.success(request, '已清理所有執行紀錄。')
    except BackendAPIError as exc:
        messages.error(request, f'清理失敗：{exc}')
    return redirect('job_runs')


def job_run_logs_view(request, run_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        logs = demo_store.get_logs(request, run_id) if settings.DEMO_MODE else _client(request).get_run_logs(run_id)
        logs = logs if isinstance(logs, list) else logs.get('items', [])
    except BackendAPIError as exc:
        messages.error(request, str(exc))
        logs = []
    return render(request, 'ui/logs.html', {'logs': logs, 'run_id': run_id})


@require_POST
def job_retry_view(request, run_id):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    try:
        if settings.DEMO_MODE:
            demo_store.retry_run(request, run_id)
        else:
            _client(request).retry_run(run_id)
        messages.success(request, '已送出 Retry。')
    except BackendAPIError as exc:
        messages.error(request, str(exc))
    return redirect('job_runs')


def health_view(request):
    redirect_response = _require_login(request)
    if redirect_response:
        return redirect_response
    health = {'api': 'demo-ok', 'mode': 'demo'}
    if not settings.DEMO_MODE:
        try:
            health = _client(request).health()
        except BackendAPIError as exc:
            health = {'api': 'error', 'message': str(exc)}
    return render(request, 'ui/health.html', {'health': health})
