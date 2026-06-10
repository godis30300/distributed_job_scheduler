#!/bin/bash
# Chaos Engineering Test Script
# 模擬 Worker Pod 突然失效

NAMESPACE="job-scheduler"

echo "🧪 Starting Chaos Test..."
echo "⏳ Waiting 30 seconds for load test to stabilize..."
sleep 30

# 獲取一個隨機的 Worker Pod
TARGET_POD=$(kubectl get pods -n $NAMESPACE -l app=worker -o jsonpath='{.items[0].metadata.name}')

if [[ -z "$TARGET_POD" ]]; then
    echo "❌ No worker pods found!"
    exit 1
fi

echo "💥 CRASHING Worker Pod: $TARGET_POD"
kubectl delete pod $TARGET_POD -n $NAMESPACE --force --grace-period=0

echo "✅ Pod deleted. System should now handle the interrupted jobs."
echo "👀 Watch the Locust UI and Logs to see if jobs are re-allocated."

# 監控 Pod 重啟
kubectl get pods -n $NAMESPACE -w
