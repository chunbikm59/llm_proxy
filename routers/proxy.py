"""通用 LLM 代理轉發路由"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_db, ApiKey, UsageLog
import httpx

TZ_LOCAL = timezone(timedelta(hours=8))
LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_MASTER_KEY = "sk-litellm-master"

security = HTTPBearer(auto_error=False)

router = APIRouter(tags=["Proxy"])


def estimate_tokens(text: str) -> int:
    """根據中英文字元比例估算 token 數"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


async def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """驗證 virtual key"""
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


async def _log_usage(api_key, model, input_tokens, output_tokens, total_tokens, cost_usd, request_type="chat"):
    """記錄使用統計"""
    now = datetime.now(TZ_LOCAL)
    today = now.strftime("%Y-%m-%d")
    created_at = now.isoformat()

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


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
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

    try:
        is_stream = bool(json.loads(body).get("stream")) if body else False
    except Exception:
        is_stream = b'"stream": true' in body or b'"stream":true' in body
    client: httpx.AsyncClient = request.app.state.http_client

    request_type = "embedding" if path.lower().endswith("embeddings") else "chat"

    # ── Streaming 路徑 ──────────────────────────────────────────────────────
    if is_stream:
        # 注入 stream_options 讓 LiteLLM 在最後附上 usage chunk
        try:
            body_json = json.loads(body)
            body_json.setdefault("stream_options", {})["include_usage"] = True
            body = json.dumps(body_json).encode()
            headers.pop("content-length", None)
        except Exception:
            pass

        req = client.build_request(method=request.method, url=url, headers=headers, content=body)
        upstream_response = await client.send(req, stream=True)

        response_headers = {
            k: v for k, v in upstream_response.headers.items()
            if k.lower() not in ("transfer-encoding", "content-encoding")
        }

        log_key = key_info["key"]
        try:
            stream_model = json.loads(body).get("model") or ""
        except Exception:
            stream_model = ""
        if not stream_model:
            await upstream_response.aclose()
            return JSONResponse(status_code=400, content={"error": "missing 'model' field in request body"})
        should_log = upstream_response.status_code < 400

        # 從 request body 提取 messages 文字，用於中斷時估算 input tokens
        try:
            req_messages = json.loads(body).get("messages") or []
            input_text = " ".join(m.get("content", "") for m in req_messages if isinstance(m.get("content"), str))
        except Exception:
            input_text = ""

        async def stream_gen():
            last_usage: list = [{}]
            collected_content: list = [""]

            def _parse_chunk(chunk: bytes):
                try:
                    for line in chunk.decode("utf-8", errors="ignore").splitlines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload in ("", "[DONE]"):
                            continue
                        data = json.loads(payload)
                        if data.get("usage"):
                            last_usage[0] = data["usage"]
                        for c in (data.get("choices") or []):
                            content = (c.get("delta") or {}).get("content")
                            if content:
                                collected_content[0] += content
                except Exception:
                    pass

            try:
                async for chunk in upstream_response.aiter_bytes(chunk_size=None):
                    _parse_chunk(chunk)
                    yield chunk
            finally:
                await upstream_response.aclose()
                if should_log:
                    usage = last_usage[0]
                    if usage:
                        input_tokens  = usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0)
                        total_tokens  = usage.get("total_tokens", 0) or (input_tokens + output_tokens)
                    else:
                        input_tokens  = estimate_tokens(input_text)
                        output_tokens = estimate_tokens(collected_content[0])
                        total_tokens  = input_tokens + output_tokens
                    asyncio.get_event_loop().create_task(_log_usage(
                        api_key=log_key,
                        model=stream_model,
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
    try:
        model = json.loads(body).get("model") or ""
    except Exception:
        model = ""
    if not model:
        return JSONResponse(status_code=400, content={"error": "missing 'model' field in request body"})

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
    except Exception:
        pass

    # 3. 最終 fallback：用字元比例估算
    if total_tokens == 0:
        if request_type == "embedding":
            try:
                req_input = json.loads(body).get("input") or ""
                if isinstance(req_input, list):
                    fallback_text = " ".join(str(s) for s in req_input)
                else:
                    fallback_text = str(req_input)
            except Exception:
                fallback_text = body.decode("utf-8", errors="ignore")
        else:
            try:
                req_messages = json.loads(body).get("messages") or []
                fallback_text = " ".join(m.get("content", "") for m in req_messages if isinstance(m.get("content"), str))
            except Exception:
                fallback_text = body.decode("utf-8", errors="ignore")
        input_tokens = estimate_tokens(fallback_text)
        total_tokens = input_tokens
        print(f"[DEBUG] {request_type} fallback: text='{fallback_text[:50]}...' tokens={input_tokens}", flush=True)

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
