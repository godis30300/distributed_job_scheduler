# 分散式工作調度系統 - 壓力測試指南 (Locust)

本專案使用 [Locust](https://locust.io/) 進行壓力測試，模擬高併發的工作任務 (Job) 啟動、執行以及各種失敗場景 (Failures)，以驗證系統穩定性。

## 測試內容
- **併發衝擊 (Burst Mode)**：一次性觸發多個任務。
- **失敗情境模擬**：
  - `fail-exit`: 腳本執行返回非零狀態碼 (exit 1)。
  - `fail-timeout`: 任務執行超過設定的超時時間。
  - `fail-dir`: 指向不存在的工作目錄。
- **背景負載**：正常的成功任務與頻繁的 Dashboard 狀態查詢。

---

## 方案 A：使用 Docker Compose (本地快速測試)

這是最簡單的測試方式，適合在開發環境驗證邏輯。

1. **啟動測試環境**：
   此腳本會自動擴展 Worker 數量至 3 個，並啟動 Locust 容器。
   ```bash
   ./scripts/run_load_test.sh
   ```

2. **進入測試介面**：
   打開瀏覽器存取 [http://localhost:8089](http://localhost:8089)

3. **停止測試**：
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.load-test.yml down
   ```

---

## 方案 B：使用 Kubernetes (模擬真實生產壓力)

適合在 Minikube 或雲端 K8s 叢集測試系統極限。

### 1. 準備映像檔 (Minikube 專用)
如果您使用 Minikube，需要先將映像檔建置並載入叢集：
```bash
# 建置資料庫 (包含 Schema 初始化腳本)
docker build -t registry.git.hsnl.tw/native_cloud/distributed_job_scheduler/db:1.0.0 ./backend/database
minikube image load registry.git.hsnl.tw/native_cloud/distributed_job_scheduler/db:1.0.0

# 建置後端 (包含 Locust 測試工具)
docker build -t registry.git.hsnl.tw/native_cloud/distributed_job_scheduler/backend:1.0.0 ./backend
minikube image load registry.git.hsnl.tw/native_cloud/distributed_job_scheduler/backend:1.0.0
```

### 2. 部署測試組件
使用 `envsubst` 注入環境變數並套用設定：
```bash
# 確保環境變數已載入
export $(grep -v '^#' .env | xargs)
export JOB_SCHEDULER_POSTGRES_PASSWORD=$POSTGRES_PASSWORD
export JOB_SCHEDULER_JWT_SECRET_KEY=$JWT_SECRET_KEY
export JOB_SCHEDULER_DATABASE_URL="postgresql+psycopg2://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB"

# 套用 K8s 設定
envsubst < deploy/k8s/01-config.yaml | kubectl apply -f -
kubectl apply -f deploy/k8s/08-locust.yaml
```

### 3. 開啟測試控制台
```bash
kubectl port-forward svc/locust 8089:8089 -n job-scheduler
```
打開瀏覽器存取 [http://localhost:8089](http://localhost:8089)

---

## 如何判讀結果？

1. **Failures 標籤頁**：
   您會看到刻意構造的 `fail-exit` 等錯誤。這證明了您的系統能正確偵測並記錄任務失敗，而不會導致整個後端崩潰。

2. **Charts 標籤頁**：
   - **Response Times**: 觀察在高併發下，API 回應是否保持在可接受範圍 (如 < 500ms)。
   - **Total Requests per Second**: 觀察系統每秒能處理多少個 Job 啟動請求。

3. **擴展壓力**：
   如果您想加大壓力，可以調整 K8s 部署中的 replicas：
   ```bash
   kubectl scale deployment locust --replicas=5 -n job-scheduler
   ```

---

## 注意事項
- **帳號生成**：Locust 會自動建立以 `stress_` 開頭的隨機帳號進行測試，不會干擾現有資料。
- **修改指令碼**：若需修改測試邏輯，請編輯 `deploy/k8s/08-locust.yaml` 中的 ConfigMap 部分，然後重新套用即可。
