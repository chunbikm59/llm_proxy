# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Virtual Key Management Proxy — a FastAPI service that manages virtual API keys, tracks usage, and proxies requests to LiteLLM (which then forwards to actual LLM providers like OpenAI, Anthropic, or local models via LM Studio).

**Request flow:**
```
Client (virtual key) → FastAPI :1235 → LiteLLM subprocess :4000 → LLM provider
                              ↕
                         PostgreSQL (proxy.db via PROXY_DATABASE_URL)
```

## Commands

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run server (port 1235)
python main.py

# Run tests
python -m pytest test/test_key_crud.py -v
python -m pytest test/test_stream.py -v
python -m pytest test/test_concurrent.py -v
python -m pytest test/test_embedding.py -v
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server (hot reload, proxies /admin to :8000)
npm run dev

# Build to ../static/ (served by FastAPI)
npm run build
```

## Architecture

### Backend (`main.py`, `db.py`, `models.py`)

- **main.py** — FastAPI app on port 8000. Handles virtual key auth, request proxying, streaming/non-streaming responses, usage tracking, and system monitoring. Also manages the LiteLLM subprocess lifecycle.
- **db.py** — SQLAlchemy models: `ApiKey` (key metadata + cumulative stats) and `UsageLog` (per-request breakdown). Tables auto-created on startup via `init_db()`.
- **models.py** — Pydantic schemas: `KeyCreate` (request), `KeyInfo` (response).
- **litellm_config.yaml** — Model definitions pointing to LM Studio at `http://127.0.0.1:1234/v1`.

**Key endpoints:**
- `POST/GET/PATCH/DELETE /admin/keys/*` — virtual key CRUD
- `GET /admin/system/stats` — CPU/RAM/GPU metrics via psutil + pynvml
- `/{path:path}` (all methods) — universal proxy route

**Token estimation priority:** LiteLLM response header `x-litellm-usage` → response body `usage` field → character-based fallback (Chinese: 1.5 chars/token, other: 4 chars/token).

**Timezone:** UTC+8 hardcoded throughout.

### Frontend (`frontend/src/`)

Vue 3 + TypeScript SPA, built with Vite, styled with Tailwind CSS v4.

- **views/** — `KeysView`, `UsageView`, `MonitoringView` (three main pages)
- **components/keys/** — `CreateKeyDialog`, `EditKeyDialog`, `KeyUsageDialog`
- **components/monitoring/** — `GaugeCard` for system metrics
- **components/ui/** — shadcn/ui components (Radix Vue based)
- **composables/** — `useKeys`, `useRates`, `useUsageData`, `useConfirmDialog`
- **api/index.ts** — HTTP client calling FastAPI `/admin/*` endpoints

Built output goes to `../static/`, which FastAPI mounts and serves. In production, access at `http://localhost:1235`; in dev, Vite at `http://localhost:5173` proxies API calls.

## Environment

Create a `.env` file (see `.env.example`):
```
PROXY_DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, LiteLLM, HTTPX |
| Monitoring | psutil, pynvml |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS v4 |
| UI Components | Radix Vue (shadcn/ui style) |
| Charts | ECharts |
| Database | PostgreSQL |
