# LLM Virtual Key Proxy

LiteLLM（無 DB）前面加一層 FastAPI，負責 virtual key 管理與用量記錄。

## 架構

```
Client（virtual key）
    ↓  port 8000
FastAPI Proxy  ←── proxy.db（SQLite）
    ↓  port 4000  master key
LiteLLM Proxy
    ↓
真實 LLM API
```

## 安裝

```bash
pip install -r requirements.txt
```

## 啟動

### 1. 先啟動 LiteLLM（無 DB 版）

```bash
# 設定你的 LLM API key
set OPENAI_API_KEY=sk-...         # Windows
# export OPENAI_API_KEY=sk-...   # Linux/Mac

litellm --config litellm_config.yaml --port 4000
```

### 2. 再啟動 FastAPI Proxy

```bash
uvicorn main:app --port 8000 --reload
```

---

## API 使用方式

### 產生 Virtual Key

```bash
curl -X POST http://localhost:8000/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "team-a"}'
```

回傳：
```json
{
  "id": 1,
  "key": "sk-xxxxxxxxxxxxxxxx",
  "name": "team-a",
  "created_at": "2026-03-21T10:00:00",
  "is_active": 1,
  "total_requests": 0,
  "total_tokens": 0,
  "total_cost_usd": 0.0
}
```

### 列出所有 Keys（含累計用量）

```bash
curl http://localhost:8000/admin/keys
```

### 查詢某 Key 的每日用量明細

```bash
curl http://localhost:8000/admin/keys/sk-xxx/usage
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

### 停用 Key

```bash
curl -X DELETE http://localhost:8000/admin/keys/sk-xxx
```

---

## 呼叫 LLM（用 Virtual Key）

完全相容 OpenAI SDK，只要把 base_url 指到你的 proxy：

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-你的virtual-key",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

或用 curl：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-你的virtual-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 新增 LLM Provider

編輯 `litellm_config.yaml`：

```yaml
model_list:
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
```

重啟 LiteLLM 即可，FastAPI proxy 完全不用改。
