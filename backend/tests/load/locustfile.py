import time
import random
import string
import os
import uuid
from locust import HttpUser, task, between

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class JobSchedulerUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.username = f"locust_{random_string()}"
        # 安全修正：不使用硬編碼密碼
        self.password = os.getenv("LOCUST_TEST_PASSWORD", "DefaultTestPass123!")
        self.headers = {}
        self._authenticate()

    def _authenticate(self):
        reg_data = {
            "username": self.username,
            "email": f"{self.username}@example.com",
            "password": self.password,
            "role": "operator"
        }
        self.client.post("/api/auth/register", json=reg_data)

        login_data = {"username": self.username, "password": self.password}
        with self.client.post("/api/auth/login", json=login_data) as resp:
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {token}"}

    @task(3)
    def dashboard(self):
        self.client.get("/api/dashboard/summary", headers=self.headers, name="/dashboard/summary")

    @task(2)
    def jobs(self):
        self.client.get("/api/jobs", headers=self.headers, name="/jobs")
        self.client.get("/api/job-runs", headers=self.headers, name="/job-runs")

    @task(1)
    def run_job(self):
        name = f"job-{random_string()}"
        # 安全修正：使用唯一的相對路徑作為工作目錄，避開 /tmp 根目錄
        safe_work_dir = f"locust-basic-{uuid.uuid4().hex[:12]}"
        
        payload = {
            "name": name,
            "task_type": "shell",
            "script": "sleep 1",
            "description": "locust",
            "working_dir": safe_work_dir,
            "schedule_type": "manual",
            "timeout_seconds": 60,
            "retry_limit": 0,
            "status": "enabled"
        }
        with self.client.post("/api/jobs", json=payload, headers=self.headers) as resp:
            if resp.status_code in [200, 201]:
                jid = resp.json().get("id")
                self.client.post(f"/api/jobs/{jid}/run", headers=self.headers)
