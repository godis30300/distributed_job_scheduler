# Frontend 開發者詳細手冊

本文件專為前端開發人員編寫，詳述專案架構、後端 API 整合流程以及各模組的具體職責。

---

## 1. 目錄結構與職責分工

`frontend/` 目錄採用 Django 框架，其核心邏輯與資源分配如下：

### 核心管理 (`scheduler_frontend/`)
*   **`settings.py`**: 專案的全域設定中心。
    *   `BACKEND_API_URL`: 設定後端 FastAPI 的基礎路徑。
    *   `DEMO_MODE`: 控制系統是否處於「純前端示範模式」。
    *   `DATABASES`: 這裡的 SQLite 僅用於儲存 Django 內部的 Session（登入狀態）與快取，不儲存業務資料。
*   **`urls.py`**: 頂層路由配置，將 `/` 開頭的請求導向 `ui` 應用。

### 業務應用 (`ui/`)
*   **`templates/ui/`**: **HTML 模板目錄**
    *   `base.html`: 定義了導覽列、側邊欄與樣式引入的基礎模板。
    *   `partials/`: 存放重複使用的 HTML 片段（如 `job_table.html`），透過 `{% include %}` 嵌入各頁面。
*   **`static/ui/`**: **靜態資源**
    *   `styles.css`: 所有的 UI 視覺樣式、佈局微調皆在此定義。
*   **`api_client.py`**: **API 通訊層**
    *   封裝了 `requests` 庫。
    *   負責處理 Bearer Token 的帶入、HTTP 錯誤碼的初步攔截與 JSON 解析。
    *   **資料庫串接的核心**：前端所有資料皆透過此處的方法與後端交換。
*   **`views.py`**: **頁面控制器 (Controller)**
    *   負責處理使用者的 GET/POST 請求。
    *   根據 `DEMO_MODE` 開關，決定從 `demo_store.py` 讀取假資料，還是從 `api_client.py` 呼叫真實 API。
    *   資料清洗：在此處將 API 回傳的原始資料轉換為模板易於顯示的格式。
*   **`forms.py`**: **表單定義**
    *   定義建立 Job 或編輯 Job 時需要的欄位校驗（Validation）。
*   **`demo_store.py`**: **Mock Data 中心**
    *   當後端開發尚未完成或需要離線展示時，此檔案模擬了 API 的回傳結果。

---

## 2. 後端 API 與資料串接指南

前端與資料庫的「串接」並非直接連線 DB，而是透過 **API 抽象層**。

### A. 整合配置
在 `scheduler_frontend/settings.py` 中，確保以下設定正確：
```python
# 開發環境建議先設為 True 確認 UI 沒問題，整合時改為 False
DEMO_MODE = False 

# 指向你的後端容器或主機位址
BACKEND_API_URL = "http://localhost:8000/api"
```

### B. 身份驗證流程 (JWT)
1.  使用者在 `login` 頁面送出帳密。
2.  `views.py` 呼叫 `api_client.login()`。
3.  後端回傳 `access_token`。
4.  `views.py` 將 token 存入 **Django Session** (`request.session['token'] = ...`)。
5.  後續所有請求，`api_client` 會自動從 session 取出 token 並放入 Header：
    `Authorization: Bearer <token>`

### C. 實作一個新的資料顯示頁面
1.  **後端**: 確認 FastAPI 已有對應的 Endpoint（例如 `GET /api/system/stats`）。
2.  **`api_client.py`**: 新增對應方法：
    ```python
    def get_stats(self):
        return self._request('GET', '/system/stats')
    ```
3.  **`views.py`**: 在對應的 View 函數中呼叫：
    ```python
    def stats_view(request):
        client = BackendAPIClient(token=request.session.get('token'))
        data = client.get_stats()
        return render(request, 'ui/stats.html', {'stats': data})
    ```
4.  **`templates/ui/stats.html`**: 使用 `{{ stats.some_field }}` 顯示資料。

---

## 3. 環境與部署
*   **本地運行**: `python manage.py runserver`
*   **相依套件**: 若新增了 library（如 `chart.js` 的 Python 封裝），請記得更新 `requirements.txt`。
*   **資料庫同步**: 初次執行請務必運行 `python manage.py migrate` 以建立 Django 必備的系統表。
