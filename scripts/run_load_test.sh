#!/bin/bash

# 確保腳本在專案根目錄執行
cd "$(dirname "$0")/.."

echo "🚀 Starting Distributed Job Scheduler Load Test Environment..."

# 檢查 .env 檔案
if [ ! -f .env ]; then
    echo "⚠️  .env file not found, creating from .env.example..."
    cp .env.example .env
fi

# 啟動服務並擴展 Worker 數量以應對高併發
docker-compose -f docker-compose.yml -f docker-compose.load-test.yml up -d --build --scale worker=3

echo "----------------------------------------------------------"
echo "📊 Locust Load Test UI: http://localhost:8089"
echo "🖥️  Backend API: http://localhost:8000"
echo "----------------------------------------------------------"
echo "To run headless test (e.g., 50 users, 10 spawn rate, 2 mins):"
echo "docker-compose -f docker-compose.yml -f docker-compose.load-test.yml exec locust locust -f /app/tests/load/locustfile_advanced.py --host http://backend:8000 --headless -u 50 -r 10 --run-time 2m"
echo "----------------------------------------------------------"
echo "Logs can be viewed with: docker-compose logs -f locust"
echo "Stop the test with: docker-compose -f docker-compose.yml -f docker-compose.load-test.yml down"
