import time
import random
import string
import uuid
from locust import HttpUser, task, between, events, tag

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class AdvancedJobSchedulerUser(HttpUser):
    wait_time = between(0.5, 2)  # 縮短等待時間以增加壓力
    
    def on_start(self):
        self.username = f"stress_{random_string()}"
        self.password = "password123"
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

    def _create_and_run_job(self, name_prefix, script, timeout=60, working_dir="/tmp", expect_failure=False):
        name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": name,
            "task_type": "shell",
            "script": script,
            "description": "stress-test",
            "working_dir": working_dir,
            "schedule_type": "manual",
            "timeout_seconds": timeout,
            "retry_limit": 1,
            "status": "enabled"
        }
        
        with self.client.post("/api/jobs", json=payload, headers=self.headers, name=f"/jobs [create {name_prefix}]") as resp:
            if resp.status_code in [200, 201]:
                jid = resp.json().get("id")
                with self.client.post(f"/api/jobs/{jid}/run", headers=self.headers, name=f"/jobs/run [{name_prefix}]") as run_resp:
                    if run_resp.status_code in [200, 201]:
                        return run_resp.json().get("run_id")
        return None

    @tag('success')
    @task(10)
    def stress_success_jobs(self):
        """正常工作的穩定壓力"""
        self._create_and_run_job("success", "echo 'hello' && sleep 0.5")

    @tag('failure')
    @task(5)
    def stress_exit_failure(self):
        """模擬腳本執行失敗 (exit 1)"""
        self._create_and_run_job("fail-exit", "exit 1", expect_failure=True)

    @tag('failure')
    @task(3)
    def stress_timeout_failure(self):
        """模擬超時失敗"""
        self._create_and_run_job("fail-timeout", "sleep 10", timeout=1, expect_failure=True)

    @tag('failure')
    @task(2)
    def stress_invalid_dir(self):
        """模擬無效目錄失敗"""
        self._create_and_run_job("fail-dir", "ls", working_dir="/non/existent/path", expect_failure=True)

    @tag('burst')
    @task(1)
    def burst_trigger(self):
        """併發衝擊：一次觸發多個工作"""
        for i in range(5):
            self._create_and_run_job(f"burst-{i}", "echo 'burst'")

    @task(5)
    def monitor_status(self):
        """模擬用戶頻繁檢查狀態"""
        self.client.get("/api/dashboard/summary", headers=self.headers, name="/dashboard/summary")
        self.client.get("/api/job-runs?limit=20", headers=self.headers, name="/job-runs")
        self.client.get("/api/metrics", name="/metrics")
