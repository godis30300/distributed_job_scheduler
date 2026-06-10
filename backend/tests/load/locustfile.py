import time
import random
import string
from locust import HttpUser, task, between

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class JobSchedulerUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.username = f"locust_{random_string()}"
        self.password = "pass123"
        self.token = None
        self.headers = {}
        
        reg_data = {
            "username": self.username,
            "email": f"{self.username}@example.com",
            "password": self.password,
            "role": "operator"
        }
        with self.client.post("/api/auth/register", json=reg_data, catch_response=True) as resp:
            if resp.status_code in [200, 201]:
                resp.success()
            else:
                resp.failure(f"Reg failed: {resp.status_code}")
                return

        login_data = {"username": self.username, "password": self.password}
        with self.client.post("/api/auth/login", json=login_data, catch_response=True) as resp:
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                resp.success()
            else:
                resp.failure(f"Login failed: {resp.status_code}")

    @task(3)
    def dashboard(self):
        self.client.get("/api/dashboard/summary", headers=self.headers, name="/dashboard/summary")
        self.client.get("/api/metrics", name="/metrics")

    @task(2)
    def jobs(self):
        self.client.get("/api/jobs", headers=self.headers, name="/jobs")
        self.client.get("/api/job-runs", headers=self.headers, name="/job-runs")

    @task(1)
    def run_job(self):
        name = f"job-{random_string()}"
        payload = {
            "name": name,
            "task_type": "shell",
            "script": "sleep 1",
            "description": "locust",
            "working_dir": "/tmp",
            "schedule_type": "manual",
            "timeout_seconds": 60,
            "retry_limit": 0,
            "status": "enabled"
        }
        with self.client.post("/api/jobs", json=payload, headers=self.headers, catch_response=True) as resp:
            if resp.status_code in [200, 201]:
                jid = resp.json().get("id")
                with self.client.post(f"/api/jobs/{jid}/run", headers=self.headers, catch_response=True) as r_resp:
                    if r_resp.status_code in [200, 201]:
                        r_resp.success()
                    else:
                        r_resp.failure("Run failed")
            else:
                resp.failure("Create failed")

    @task(1)
    def health(self):
        self.client.get("/api/health", name="/health")
