# LLM Virtual Key Proxy

以 FastAPI 構建的本地 AI 服務管理代理層，整合虛擬金鑰管理、llama.cpp 模型實例管理、Whisper.cpp 語音轉錄 Cluster 管理，並附有完整的 Vue 3 Web 管理介面。

## 專案動機

在本地架設 LLM / ASR 服務供多人共用時，難以按使用者個別追蹤用量與成本，也缺乏統一的服務管理入口。本專案在本地模型服務前架設代理層，發行虛擬金鑰給各使用者，統一收攏所有請求並記錄用量，同時提供 Web UI 管理 llama.cpp 與 whisper.cpp 的完整生命週期。

## 功能亮點

- **虛擬金鑰管理** — 建立、停用、啟用、永久刪除虛擬 API 金鑰
- **用量追蹤** — 每筆請求記錄 Token 數與成本（依模型套用自訂費率）
- **多粒度用量查詢** — 按金鑰 / 日期 / 模型維度彙整，支援批次查詢
- **串流代理** — 完整支援 OpenAI SSE 串流格式透傳
- **系統監控** — 即時 CPU、RAM、GPU（NVML）指標
- **llama.cpp 實例管理** — 從 Web UI 啟動 / 停止本地模型 subprocess，即時查看 log
- **Whisper Cluster 管理** — 以 Cluster 概念管理 whisper.cpp，支援並發控制與即時串流轉錄
- **OpenAI 相容介面** — 客戶端零改動，只需替換 `base_url`

## 系統架構

```
Client（virtual key）
    ↓  :1235
FastAPI Proxy  ←── PostgreSQL（用量 / 金鑰 / 實例資料）
    ├─→ LiteLLM Proxy（subprocess，自動啟動）:4000
    │       ↓
    │   本地 llama.cpp 實例，或雲端 API（OpenAI / Anthropic…）
    │
    ├─→ llama.cpp subprocess（每個實例獨立管理）
    │
    └─→ whisper.cpp subprocess（每次轉錄請求按需啟動）
```

FastAPI 啟動時自動以 subprocess 方式啟動 LiteLLM，llama.cpp 實例依設定自動啟動，whisper.cpp 則按請求動態啟動。

## 技術棧

| 層次 | 技術 |
|------|------|
| Backend | Python、FastAPI、SQLAlchemy、LiteLLM、HTTPX |
| 監控 | psutil、pynvml |
| 音訊處理 | ffmpeg（自動格式轉換）、whisper.cpp（推論） |
| Frontend | Vue 3、TypeScript、Vite、Tailwind CSS v4 |
| UI 元件 | Radix Vue（shadcn/ui 風格） |
| 圖表 | ECharts |
| 資料庫 | PostgreSQL（透過 SQLAlchemy ORM 存取，僅需修改 `DATABASE_URL` 即可切換至 SQLite、MySQL 等任何 SQLAlchemy 支援的資料庫） |
| Schema 管理 | Alembic migration |

## 目錄結構

```
├── main.py                       # FastAPI 入口，lifespan 管理所有服務
├── db.py                         # SQLAlchemy 模型（ApiKey、UsageLog、LlamaCppInstance、WhisperCluster、WhisperTranscriptionJob）
├── llama_manager.py              # llama.cpp subprocess 生命週期管理
├── whisper_manager.py            # Whisper Cluster 管理 + 轉錄 API router
├── routers/
│   ├── keys.py                   # 虛擬金鑰 CRUD
│   ├── proxy.py                  # 請求代理 + 用量記錄
│   ├── monitoring.py             # 系統資源監控
│   └── whisper_transcription.py  # POST /v1/audio/transcriptions
├── migrations/                   # Alembic migration 版本管理
├── frontend/src/
│   ├── views/                    # KeysView、UsageView、MonitoringView、LlamaView、WhisperView
│   ├── components/               # 各功能子元件（含 Whisper Cluster Dialog）
│   ├── composables/              # useKeys、useRates、useLlamaInstances、useWhisperClusters
│   └── api/index.ts              # HTTP 客戶端
├── litellm_config.yaml           # LiteLLM 模型定義
└── test/                         # pytest 測試套件
```

## 安裝與啟動

```bash
# Backend
pip install -r requirements.txt

# 建立 .env（參考 .env.example）
echo "PROXY_DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname" > .env

# 執行 DB migration
python -m alembic upgrade head

# Frontend 打包（輸出至 ../static/，由 FastAPI 直接提供）
cd frontend && npm install && npm run build

# 啟動（監聽 :1235）
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
| Whisper | 管理 Whisper Cluster 設定，查看轉錄歷史 |

## Whisper Cluster 架構

Whisper 採用 **Cluster 架構**，與傳統長駐進程不同：

- **Cluster** = 一組設定（執行檔路徑、模型、推論參數）+ 最大並發數（`max_instances`）+ `is_default` 標記
- 每次 `POST /v1/audio/transcriptions` 按需啟動一個 `whisper.cpp` subprocess，轉錄完成即結束
- 超過 `max_instances` → 立即回傳 `429`，不排隊
- 不指定 `cluster` 參數時自動使用標記為 `is_default` 的 Cluster
- 客戶端斷線時立即 kill subprocess，釋放並發名額

### 音訊格式處理

接收任意格式音訊（MP3、M4A、OGG 等），自動透過 `ffmpeg` 轉換為 whisper.cpp 所需的 WAV（16kHz、mono、16-bit PCM）。WAV 格式直接送入，跳過轉換。

## API 使用

### 語音轉錄（OpenAI 相容）

```bash
# 非串流：等轉錄完成後一次回傳
curl -X POST http://localhost:1235/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1"

# NDJSON 串流：每個 segment 完成即推送一行
curl -N -X POST http://localhost:1235/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "stream=true"

# 指定特定 Cluster
curl -X POST http://localhost:1235/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "cluster=fast"
```

串流回傳格式（NDJSON，每行一個 segment）：
```
{"text": "[00:00:00.000 --> 00:00:04.100]  逐字稿內容"}
{"text": "[00:00:04.100 --> 00:00:08.300]  下一個段落"}
```

### 虛擬金鑰管理

```bash
# 建立金鑰
curl -X POST http://localhost:1235/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "team-a", "description": "Team A 開發用"}'

# 列出所有金鑰
curl http://localhost:1235/admin/keys

# 查詢金鑰每日用量
curl http://localhost:1235/admin/keys/{key_id}/usage

# 停用 / 啟用 / 永久刪除
curl -X DELETE http://localhost:1235/admin/keys/{key_id}
curl -X POST http://localhost:1235/admin/keys/{key_id}/activate
curl -X DELETE http://localhost:1235/admin/keys/{key_id}/permanent
```

### Whisper Cluster 管理

```bash
# 建立 Cluster（設為預設，最多 2 個並發）
curl -X POST http://localhost:1235/whisper/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "default",
    "executable_path": "D:/Apps/whisper-cublas/whisper-cli.exe",
    "model_path": "D:/models/ggml-large-v2-q8_0.bin",
    "max_instances": 2,
    "is_default": true
  }'

# 列出所有 Cluster（含即時 active_count）
curl http://localhost:1235/whisper/clusters

# 更新設定
curl -X PATCH http://localhost:1235/whisper/clusters/default \
  -H "Content-Type: application/json" \
  -d '{"max_instances": 3}'

# 轉錄歷史
curl http://localhost:1235/whisper/jobs
```

### LLM 呼叫

介面完全相容 OpenAI SDK：

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

編輯 `litellm_config.yaml` 後重啟即可：

```yaml
model_list:
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: local-llama
    litellm_params:
      model: openai/local-llama
      api_base: http://127.0.0.1:8080/v1
      api_key: none
```
