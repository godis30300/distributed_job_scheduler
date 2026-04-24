#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://localhost:8000}"

curl -s -X POST "$API/api/auth/register"   -H "Content-Type: application/json"   -d '{"username":"admin","password":"admin123","role":"admin"}' || true

TOKEN=$(curl -s -X POST "$API/api/auth/login"   -H "Content-Type: application/json"   -d '{"username":"admin","password":"admin123"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "TOKEN=$TOKEN"

JOB_ID=$(curl -s -X POST "$API/api/jobs"   -H "Content-Type: application/json"   -H "Authorization: Bearer $TOKEN"   -d '{
    "task_name":"hello-script",
    "action_type":"shell",
    "action_payload":{"script":"hello.sh","args":[]},
    "schedule_rule":"every:5m",
    "timeout_seconds":60,
    "max_retry":3
  }' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')

echo "JOB_ID=$JOB_ID"

curl -s -X POST "$API/api/jobs/$JOB_ID/trigger"   -H "Authorization: Bearer $TOKEN" | jq .
