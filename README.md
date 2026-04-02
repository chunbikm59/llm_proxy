# LLM Virtual Key Proxy

以 FastAPI 構建的本地 LLM 虛擬金鑰管理代理層，主要用於管理本地部署的 llama.cpp 模型，提供多租戶 API 金鑰管理、用量追蹤與成本控制，並附有完整的 Vue 3 Web 管理介面。亦支援透過 LiteLLM 串接雲端 API（OpenAI、Anthropic 等）。

## 專案動機

在本地架設 LLM 服務（如 llama.cpp）供多人共用時，難以按使用者個別追蹤用量與成本。本專案在本地模型服務前架設代理層，發行虛擬金鑰給各使用者，統一收攏所有請求並記錄用量，實現細粒度的成本可視化與資源管控。

## 功能亮點

- **虛擬金鑰管理** — 建立、停用、啟用、永久刪除虛擬 API 金鑰
- **用量追蹤** — 每筆請求記錄 Token 數與成本（依模型套用自訂費率）
- **多粒度用量查詢** — 按金鑰 / 日期 / 模型維度彙整，支援批次查詢
- **串流代理** — 完整支援 OpenAI SSE 串流格式透傳
- **系統監控** — 即時 CPU、RAM、GPU（NVML）指標
- **llama.cpp 實例管理** — 從 Web UI 啟動 / 停止本地模型 subprocess，即時查看 log
- **OpenAI 相容介面** — 客戶端零改動，只需替換 `base_url`

## 系統架構

```
Client（virtual key）
    ↓  :1235
FastAPI Proxy  ←── PostgreSQL（用量 / 金鑰資料）
    ↓  :4000（master key）
LiteLLM Proxy（subprocess，自動啟動）
    ↓
本地 llama.cpp 實例，或雲端 API（OpenAI / Anthropic…）
```

FastAPI 啟動時自動以 subprocess 方式啟動 LiteLLM，無需額外手動操作。

## 技術棧

| 層次 | 技術 |
|------|------|
| Backend | Python、FastAPI、SQLAlchemy、LiteLLM、HTTPX |
| 監控 | psutil、pynvml |
| Frontend | Vue 3、TypeScript、Vite、Tailwind CSS v4 |
| UI 元件 | Radix Vue（shadcn/ui 風格） |
| 圖表 | ECharts |
| 資料庫 | PostgreSQL |

## 目錄結構

```
├── main.py                  # FastAPI 入口，proxy 路由、串流處理
├── db.py                    # SQLAlchemy 模型（ApiKey、UsageLog、LlamaCppInstance）
├── models.py                # Pydantic schema
├── llama_manager.py         # llama.cpp subprocess 生命週期管理
├── routers/
│   ├── keys.py              # 虛擬金鑰 CRUD
│   ├── proxy.py             # 請求代理 + 用量記錄
│   └── monitoring.py        # 系統資源監控 + llama 實例管理 API
├── frontend/src/
│   ├── views/               # KeysView、UsageView、MonitoringView、LlamaView
│   ├── components/          # 各功能的子元件
│   ├── composables/         # useKeys、useRates、useUsageData、useLlamaInstances
│   └── api/index.ts         # HTTP 客戶端
├── litellm_config.yaml      # LiteLLM 模型定義
└── test/                    # pytest 測試套件
```

## 安裝與啟動

```bash
# Backend
pip install -r requirements.txt

# 建立 .env（參考 .env.example）
echo "PROXY_DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname" > .env

# Frontend 打包（輸出至 ../static/，由 FastAPI 直接提供）
cd frontend && npm install && npm run build

# 啟動（監聽 :1235，同時自動啟動 LiteLLM subprocess）
python main.py
```

Web 管理介面：`http://localhost:1235`

## Web 管理介面

| 頁面 | 功能 |
|------|------|
| Keys | 建立 / 停用 / 刪除虛擬金鑰，查看個別金鑰累計用量 |
| Usage | 按日期 + 模型的用量明細圖表，支援多金鑰批次查詢 |
| Monitoring | 即時 CPU / RAM / GPU 監控儀表板 |
| Llama | 啟動 / 停止本地 llama.cpp 實例，即時串流 log |

## Admin API

### 虛擬金鑰管理

```bash
# 建立金鑰
curl -X POST http://localhost:1235/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "team-a", "description": "Team A 開發用"}'

# 列出所有金鑰
curl http://localhost:1235/admin/keys

# 查詢金鑰每日用量（按日期 + 模型彙整）
curl http://localhost:1235/admin/keys/{key_id}/usage

# 停用金鑰（軟刪除）
curl -X DELETE http://localhost:1235/admin/keys/{key_id}

# 重新啟用
curl -X POST http://localhost:1235/admin/keys/{key_id}/activate

# 永久刪除
curl -X DELETE http://localhost:1235/admin/keys/{key_id}/permanent
```

### 系統監控

```bash
curl http://localhost:1235/admin/system/stats
```

## 使用虛擬金鑰呼叫 LLM

介面完全相容 OpenAI SDK，只需替換 `base_url` 與 `api_key`：

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-your-virtual-key",
    base_url="http://localhost:1235/v1"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## 新增 LLM Provider

編輯 `litellm_config.yaml` 後重啟即可，proxy 層不需任何修改：

```yaml
model_list:
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: local-llama
    litellm_params:
      model: openai/local-llama
      api_base: http://127.0.0.1:8080/v1
      api_key: none
```

## 測試

```bash
python -m pytest test/test_key_crud.py -v     # 金鑰 CRUD
python -m pytest test/test_stream.py -v       # 串流
python -m pytest test/test_concurrent.py -v  # 並發
python -m pytest test/test_embedding.py -v   # Embedding
```
