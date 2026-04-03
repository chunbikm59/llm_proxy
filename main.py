import asyncio
import atexit
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import init_db, LlamaCppInstance
from llama_manager import LlamaCppManager, router as llama_router
from whisper_manager import WhisperCppManager, router as whisper_router
from routers import keys, monitoring, proxy, whisper_transcription

LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_CONFIG = Path(__file__).parent / "litellm_config.yaml"
LITELLM_HEALTH_URL = f"{LITELLM_BASE_URL}/health/liveliness"


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

        manager = LlamaCppManager()
        app.state.llama_manager = manager
        await manager.startup()

        whisper_mgr = WhisperCppManager()
        app.state.whisper_manager = whisper_mgr
        await whisper_mgr.startup()

        yield

        await whisper_mgr.shutdown()
        await manager.shutdown()

    # ── Shutdown：優雅停止 LiteLLM ───────────────────────────────────────────
    litellm_proc.terminate()
    try:
        await asyncio.wait_for(litellm_proc.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        litellm_proc.kill()
        await litellm_proc.wait()


app = FastAPI(title="LLM Virtual Key Proxy", lifespan=lifespan)

# 靜態檔案（必須在通用 proxy 路由之前掛載）
_static_dir = Path(__file__).parent / "static"
(_static_dir / "assets").mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ── 註冊路由 ──────────────────────────────────────────────────────────────────
app.include_router(keys.router)
app.include_router(monitoring.router)
app.include_router(llama_router)
app.include_router(whisper_router)
app.include_router(whisper_transcription.router)
app.include_router(proxy.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1235)
