import requests
from django.conf import settings


class BackendAPIError(Exception):
    pass


class BackendAPIClient:
    def __init__(self, token=None):
        self.base_url = settings.BACKEND_API_URL.rstrip('/')
        self.token = token

    def _headers(self):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def _request(self, method, path, **kwargs):
        url = f'{self.base_url}{path}'
        headers = kwargs.pop('headers', {})
        headers = {**self._headers(), **headers}
        if 'json' in kwargs:
            headers.setdefault('Content-Type', 'application/json')
        try:
            response = requests.request(method, url, headers=headers, timeout=8, **kwargs)
        except requests.RequestException as exc:
            raise BackendAPIError(f'Cannot connect backend API: {exc}') from exc

        if response.status_code >= 400:
            if response.status_code == 401:
                raise BackendAPIError('驗證失敗（帳號或密碼錯誤）。')
            if response.status_code == 404:
                raise BackendAPIError('找不到要求的資源。')
            raise BackendAPIError(f'系統錯誤 ({response.status_code})')

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}

    def register(self, payload):
        return self._request('POST', '/auth/register', json=payload)

    def login(self, payload):
        return self._request('POST', '/auth/login', json=payload)

    def me(self):
        return self._request('GET', '/auth/me')

    def list_jobs(self):
        return self._request('GET', '/jobs')

    def get_job(self, job_id):
        return self._request('GET', f'/jobs/{job_id}')

    def create_job(self, payload):
        return self._request('POST', '/jobs', json=payload)

    def update_job(self, job_id, payload):
        return self._request('PUT', f'/jobs/{job_id}', json=payload)

    def delete_job(self, job_id):
        return self._request('DELETE', f'/jobs/{job_id}')

    def run_job(self, job_id):
        return self._request('POST', f'/jobs/{job_id}/run')

    def list_job_runs(self):
        return self._request('GET', '/job-runs')

    def get_run_logs(self, run_id):
        return self._request('GET', f'/job-runs/{run_id}/logs')

    def retry_run(self, run_id):
        return self._request('POST', f'/job-runs/{run_id}/retry')

    def health(self):
        return self._request('GET', '/health')
