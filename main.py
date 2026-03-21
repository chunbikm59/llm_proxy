import asyncio
import atexit
import json
import secrets
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from sqlalchemy import func
from db import init_db, get_db, ApiKey, UsageLog
from models import KeyCreate, KeyInfo

LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_MASTER_KEY = "sk-litellm-master"
LITELLM_CONFIG = Path(__file__).parent / "litellm_config.yaml"
LITELLM_HEALTH_URL = f"{LITELLM_BASE_URL}/health/liveliness"

security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 啟動 LiteLLM subprocess ──────────────────────────────────────────────
    litellm_bin = Path(sys.executable).parent / "litellm.exe"
    if not litellm_bin.exists():
        litellm_bin = Path(sys.executable).parent / "litellm"
    litellm_proc = await asyncio.create_subprocess_shell(
        f'"{litellm_bin}" --config "{LITELLM_CONFIG}" --port 4000 --telemetry False',
    )

    # ── atexit 保底：FastAPI 意外崩潰時也會 kill LiteLLM ────────────────────
    atexit.register(lambda: litellm_proc.returncode is None and litellm_proc.kill())

    # ── 等待 LiteLLM 就緒（最多 30 秒）─────────────────────────────────────────
    async with httpx.AsyncClient(timeout=2.0) as probe:
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                r = await probe.get(LITELLM_HEALTH_URL)
                if r.status_code == 200:
                    break
            except httpx.RequestError:
                pass
        else:
            litellm_proc.kill()
            raise RuntimeError("LiteLLM failed to start within 30 seconds")

    # ── 主要 HTTP client ─────────────────────────────────────────────────────
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    ) as client:
        app.state.http_client = client
        init_db()
        yield

    # ── Shutdown：優雅停止 LiteLLM ───────────────────────────────────────────
    litellm_proc.terminate()
    try:
        await asyncio.wait_for(litellm_proc.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        litellm_proc.kill()
        await litellm_proc.wait()


app = FastAPI(title="LLM Virtual Key Proxy", lifespan=lifespan)

# 靜態檔案（必須在通用 proxy 路由之前掛載）
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ── 驗證 virtual key ──────────────────────────────────────────────────────────

async def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key")
    api_key = credentials.credentials

    def _query():
        db = get_db()
        try:
            row = db.query(ApiKey).filter(
                ApiKey.key == api_key, ApiKey.is_active == 1
            ).first()
            return {c.name: getattr(row, c.name) for c in ApiKey.__table__.columns} if row else None
        finally:
            db.close()

    row = await asyncio.to_thread(_query)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or inactive key")
    return row


# ── Key 管理 API ──────────────────────────────────────────────────────────────

@app.post("/admin/keys", response_model=KeyInfo)
def create_key(body: KeyCreate):
    """產生一個新的 virtual key"""
    new_key = "sk-" + secrets.token_urlsafe(32)
    db = get_db()
    try:
        obj = ApiKey(
            key=new_key, name=body.name, description=body.description,
            created_at=datetime.utcnow().isoformat(), is_active=1,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/admin/keys")
def list_keys():
    """列出所有 virtual keys 及用量"""
    db = get_db()
    try:
        rows = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
        return [KeyInfo.model_validate(r) for r in rows]
    finally:
        db.close()


@app.get("/admin/keys/{key_id}/usage")
def key_usage(key_id: int):
    """查詢某個 key 的每日用量明細"""
    db = get_db()
    try:
        key_row = db.query(ApiKey.key).filter(ApiKey.id == key_id).first()
        if not key_row:
            raise HTTPException(status_code=404, detail="Key not found")
        rows = (
            db.query(
                UsageLog.date, UsageLog.model,
                func.sum(UsageLog.input_tokens).label("input_tokens"),
                func.sum(UsageLog.output_tokens).label("output_tokens"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.cost_usd).label("cost_usd"),
                func.count().label("requests"),
            )
            .filter(UsageLog.api_key == key_row.key)
            .group_by(UsageLog.date, UsageLog.model)
            .order_by(UsageLog.date.desc())
            .all()
        )
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.delete("/admin/keys/{key_id}")
def revoke_key(key_id: int):
    """停用一個 virtual key"""
    db = get_db()
    try:
        db.query(ApiKey).filter(ApiKey.id == key_id).update(
            {"is_active": 0}, synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key revoked"}


@app.post("/admin/keys/{key_id}/activate")
def activate_key(key_id: int):
    """重新啟用一個已撤銷的 virtual key"""
    db = get_db()
    try:
        updated = db.query(ApiKey).filter(ApiKey.id == key_id).update(
            {"is_active": 1}, synchronize_session=False
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Key not found")
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key activated"}


@app.delete("/admin/keys/{key_id}/permanent")
def delete_key(key_id: int):
    """永久刪除一個 virtual key 及其用量紀錄"""
    db = get_db()
    try:
        key_obj = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not key_obj:
            raise HTTPException(status_code=404, detail="Key not found")
        db.query(UsageLog).filter(UsageLog.api_key == key_obj.key).delete(synchronize_session=False)
        db.delete(key_obj)
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"message": "Key deleted permanently"}


# ── 通用 Proxy 轉發 ───────────────────────────────────────────────────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request, key_info: dict = Depends(verify_key)):
    """攔截所有請求 → 驗證 → 轉發給 LiteLLM → 記錄用量"""

    body = await request.body()

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "authorization")
    }
    headers["Authorization"] = f"Bearer {LITELLM_MASTER_KEY}"
    headers["Accept-Encoding"] = "identity"

    url = f"{LITELLM_BASE_URL}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    is_stream = b'"stream": true' in body or b'"stream":true' in body
    client: httpx.AsyncClient = request.app.state.http_client

    request_type = "embedding" if path.lower().endswith("embeddings") else "chat"

    # ── Streaming 路徑 ──────────────────────────────────────────────────────
    if is_stream:
        req = client.build_request(method=request.method, url=url, headers=headers, content=body)
        upstream_response = await client.send(req, stream=True)

        response_headers = {
            k: v for k, v in upstream_response.headers.items()
            if k.lower() not in ("transfer-encoding", "content-encoding")
        }

        log_key = key_info["key"]
        stream_model = upstream_response.headers.get("x-litellm-model-id", "unknown")
        should_log = upstream_response.status_code < 400

        async def stream_gen():
            last_usage: dict = {}
            last_model: str = stream_model
            try:
                async for chunk in upstream_response.aiter_bytes(chunk_size=None):
                    yield chunk
                    # 解析 SSE chunk，尋找含 usage 的最後一行
                    try:
                        for line in chunk.decode("utf-8", errors="ignore").splitlines():
                            if not line.startswith("data:"):
                                continue
                            payload = line[5:].strip()
                            if payload in ("", "[DONE]"):
                                continue
                            data = json.loads(payload)
                            if data.get("model"):
                                last_model = data["model"]
                            if data.get("usage"):
                                last_usage = data["usage"]
                    except Exception:
                        pass
            finally:
                await upstream_response.aclose()
                if should_log:
                    input_tokens  = last_usage.get("prompt_tokens", 0) or len(body) // 4
                    output_tokens = last_usage.get("completion_tokens", 0)
                    total_tokens  = last_usage.get("total_tokens", 0) or (input_tokens + output_tokens)
                    asyncio.get_event_loop().create_task(_log_usage(
                        api_key=log_key,
                        model=last_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost_usd=float(upstream_response.headers.get("x-litellm-response-cost", 0) or 0),
                        request_type=request_type,
                    ))

        return StreamingResponse(
            stream_gen(),
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type=upstream_response.headers.get("content-type", "text/event-stream"),
        )

    # ── 非 Streaming 路徑 ───────────────────────────────────────────────────
    upstream = await client.request(method=request.method, url=url, headers=headers, content=body)

    cost = float(upstream.headers.get("x-litellm-response-cost", 0) or 0)
    input_tokens = output_tokens = total_tokens = 0
    model = "unknown"

    # 1. 從 LiteLLM header 讀
    usage_str = upstream.headers.get("x-litellm-usage", "")
    if usage_str:
        try:
            usage = json.loads(usage_str)
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
        except Exception:
            pass

    # 2. 從 response JSON body 讀（優先，model 名稱可讀）
    try:
        resp_json = upstream.json()
        usage = resp_json.get("usage") or {}
        if not input_tokens:
            input_tokens = usage.get("prompt_tokens", 0)
        if not output_tokens:
            output_tokens = usage.get("completion_tokens", 0)
        if not total_tokens:
            total_tokens = usage.get("total_tokens", 0) or (input_tokens + output_tokens)
        model = resp_json.get("model") or "unknown"
    except Exception:
        pass

    # 3. 最終 fallback：用輸入字元數估算
    if total_tokens == 0:
        input_tokens = len(body) // 4
        total_tokens = input_tokens

    if upstream.status_code < 400:
        await _log_usage(
            api_key=key_info["key"],
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            request_type=request_type,
        )

    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in ("transfer-encoding", "content-encoding")
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


async def _log_usage(api_key, model, input_tokens, output_tokens, total_tokens, cost_usd, request_type="chat"):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    created_at = datetime.utcnow().isoformat()

    def _write():
        db = get_db()
        try:
            db.add(UsageLog(
                api_key=api_key, model=model, request_type=request_type, date=today,
                input_tokens=input_tokens, output_tokens=output_tokens,
                total_tokens=total_tokens, cost_usd=cost_usd, created_at=created_at,
            ))
            db.query(ApiKey).filter(ApiKey.key == api_key).update(
                {
                    ApiKey.total_requests: ApiKey.total_requests + 1,
                    ApiKey.total_tokens:   ApiKey.total_tokens + total_tokens,
                    ApiKey.total_cost_usd: ApiKey.total_cost_usd + cost_usd,
                },
                synchronize_session=False,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    await asyncio.to_thread(_write)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1235)
