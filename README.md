# LLM Virtual Key Proxy

LiteLLM 前置代理層，使用 FastAPI 構建，提供虛擬金鑰管理、用量追蹤與 Web 管理介面。

## 架構

```
Client（virtual key）
    ↓  port 8000
FastAPI Proxy  ←── proxy.db（SQLite）
    ↓  port 4000  master key
LiteLLM Proxy（subprocess，自動啟動）
    ↓
真實 LLM API
```

FastAPI 啟動時會自動以 subprocess 方式啟動 LiteLLM，無需手動操作。

## 安裝

```bash
pip install -r requirements.txt
```

## 啟動

```bash
uvicorn main:app --port 8000 --reload
```

啟動後：
- FastAPI Proxy：`http://localhost:8000`
- Web 管理介面：`http://localhost:8000/static/index.html`
- LiteLLM（內部）：`http://localhost:4000`（自動啟動）

---

## Web 管理介面

開啟 `http://localhost:8000/static/index.html`，功能包含：

- 建立 / 停用 / 刪除虛擬金鑰
- 查看每個金鑰的累計用量（token 數、成本）
- 按日期 + 模型查看用量明細圖表
- 自訂費率設定（儲存於 localStorage）

---

## Admin API

### 建立虛擬金鑰

```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "team-a", "description": "Team A 開發用"}'
```

回傳：
```json
{
  "id": 1,
  "key": "sk-xxxxxxxxxxxxxxxx",
  "name": "team-a",
  "description": "Team A 開發用",
  "created_at": "2026-03-21T10:00:00",
  "is_active": 1,
  "total_requests": 0,
  "total_tokens": 0,
  "total_cost_usd": 0.0
}
```

### 列出所有金鑰（含累計用量）

```bash
curl http://localhost:8000/admin/keys
```

### 查詢金鑰每日用量明細

```bash
curl http://localhost:8000/admin/keys/{key_id}/usage
```

回傳：
```json
[
  {
    "date": "2026-03-21",
    "model": "gpt-4o",
    "input_tokens": 1200,
    "output_tokens": 800,
    "total_tokens": 2000,
    "cost_usd": 0.024,
    "requests": 5
  }
]
```

### 停用金鑰（軟刪除）

```bash
curl -X DELETE http://localhost:8000/admin/keys/{key_id}
```

### 重新啟用金鑰

```bash
curl -X POST http://localhost:8000/admin/keys/{key_id}/activate
```

### 永久刪除金鑰

```bash
curl -X DELETE http://localhost:8000/admin/keys/{key_id}/permanent
```

---

## 呼叫 LLM（使用虛擬金鑰）

完全相容 OpenAI SDK，只需將 `base_url` 指向 proxy：

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-你的virtual-key",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="qwen3.5-2b@q4_k_m",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

或用 curl：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-你的virtual-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-2b@q4_k_m",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 新增 LLM Provider

編輯 `litellm_config.yaml`，重啟 FastAPI 即可：

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
```

FastAPI proxy 不需任何修改。

---

## 測試

```bash
# 金鑰管理 CRUD
python -m pytest test/test_key_crud.py -v

# 串流功能
python -m pytest test/test_stream.py -v

# 並發測試
python -m pytest test/test_concurrent.py -v
```
