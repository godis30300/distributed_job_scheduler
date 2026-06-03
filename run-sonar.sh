#!/bin/bash

set -euo pipefail

SONAR_HOST_URL="${SONAR_HOST_URL:-http://sonarqube:9000}"
SONAR_TOKEN="${SONAR_TOKEN:-}"

if [ -z "$SONAR_TOKEN" ]; then
    echo "SONAR_TOKEN is required. Export a SonarQube token before running this script."
    exit 1
fi

# 確保在 distributed_job_scheduler_default 網路中執行，這樣才能連到 sonarqube 服務
echo "Starting SonarScanner via Docker..."

docker run --rm \
    --network distributed_job_scheduler_default \
    -v "$(pwd):/usr/src" \
    -e SONAR_HOST_URL="$SONAR_HOST_URL" \
    -e SONAR_TOKEN="$SONAR_TOKEN" \
    sonarsource/sonar-scanner-cli

echo "Scan process initiated. Please check $SONAR_HOST_URL for results."
