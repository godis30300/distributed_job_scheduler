import time
import secrets
import string
import uuid
import os
from locust import HttpUser, task, between, tag

def random_string(length=8):
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length))

class AdvancedJobSchedulerUser(HttpUser):
    wait_time = between(0.5, 2)
    
    def on_start(self):
        self.username = f"stress_{random_string()}"
        self.password = os.getenv("LOCUST_TEST_PASSWORD", "DefaultTestPass123!")
        self.headers = {}
        self._authenticate()

    def _authenticate(self):
        reg_data = {
            "username": self.username,
            "email": f"{self.username}@stress.com",
            "password": self.password,
            "role": "admin"
        }
        self.client.post("/api/auth/register", json=reg_data)
        
        login_data = {"username": self.username, "password": self.password}
        with self.client.post("/api/auth/login", json=login_data) as resp:
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {token}"}

    def _create_and_run_job(self, name_prefix, script, task_type="shell", timeout=60, retry_limit=1):
        name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"
        safe_working_dir = f"locust-work-{uuid.uuid4().hex[:12]}"
        
        payload = {
            "name": name,
            "task_type": task_type,
            "script": script,
            "description": f"stress-test-{name_prefix}",
            "working_dir": safe_working_dir,
            "schedule_type": "manual",
            "timeout_seconds": timeout,
            "retry_limit": retry_limit,
            "status": "enabled"
        }
        
        with self.client.post("/api/jobs", json=payload, headers=self.headers, name=f"/jobs [create {name_prefix}]") as resp:
            if resp.status_code in [200, 201]:
                jid = resp.json().get("id")
                self.client.post(f"/api/jobs/{jid}/run", headers=self.headers, name=f"/jobs/run [{name_prefix}]")

    @tag('success')
    @task(5)
    def stress_success_jobs(self):
        """正常工作的穩定壓力"""
        self._create_and_run_job("success", "echo 'quick success' && sleep 0.1")

    @tag('long')
    @task(3)
    def stress_long_running_jobs(self):
        """長時間運行的工作 (10秒)"""
        self._create_and_run_job("long-run", "echo 'starting long job' && sleep 10 && echo 'finished'", timeout=30)

    @tag('retry')
    @task(3)
    def stress_retry_success_jobs(self):
        """第一次失敗，重試後成功的工作"""
        script = 'if [[ "$RETRY_COUNT" == "0" ]]; then echo "First attempt fail"; exit 1; else echo "Retry success"; exit 0; fi'
        self._create_and_run_job("retry-success", script, retry_limit=2)

    @tag('failure')
    @task(2)
    def stress_permanent_failure(self):
        """永久失敗的工作 (即便重試也失敗)"""
        self._create_and_run_job("perm-fail", "echo 'always fail'; exit 1", retry_limit=1)

    @task(5)
    def monitor_status(self):
        """監控 Dashboard 壓力"""
        self.client.get("/api/dashboard/summary", headers=self.headers, name="/dashboard/summary")
        self.client.get("/api/job-runs?limit=20", headers=self.headers, name="/job-runs")
