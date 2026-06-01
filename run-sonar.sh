#!/bin/bash

# 確保在 distributed_job_scheduler_default 網路中執行，這樣才能連到 sonarqube 服務
echo "Starting SonarScanner via Docker..."

docker run --rm \
    --network distributed_job_scheduler_default \
    -v "$(pwd):/usr/src" \
    sonarsource/sonar-scanner-cli

echo "Scan process initiated. Please check http://localhost:9000 for results."
