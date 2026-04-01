import asyncio
import atexit
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db import get_db, LlamaCppInstance

TZ_LOCAL = timezone(timedelta(hours=8))


# ── 資料結構 ──────────────────────────────────────────────────────────────────

class InstanceStatus(str, Enum):
    STOPPED    = "stopped"
    STARTING   = "starting"
    RUNNING    = "running"
    FAILED     = "failed"
    RESTARTING = "restarting"


@dataclass
class InstanceState:
    name:           str
    config:         dict
    proc:           Optional[asyncio.subprocess.Process] = None
    status:         InstanceStatus = InstanceStatus.STOPPED
    log_buffer:     deque = field(default_factory=lambda: deque(maxlen=500))
    drain_task:     Optional[asyncio.Task] = None
    monitor_task:   Optional[asyncio.Task] = None
    restart_count:  int = 0
    pid:            Optional[int] = None
    started_at:     Optional[str] = None


# ── Pydantic Models ───────────────────────────────────────────────────────────

class InstanceCreateRequest(BaseModel):
    name:                 str
    executable_path:      str
    model_path:           str
    host:                 str = "127.0.0.1"
    port:                 int
    context_size:         int = 4096
    n_threads:            Optional[int] = None
    n_gpu_layers:         int = 0
    parallel:             int = 1
    batch_size:           int = 512
    split_mode:           Optional[str] = None
    defrag_thold:         Optional[float] = None
    cache_type_k:         Optional[str] = None
    cache_type_v:         Optional[str] = None
    flash_attn:           bool = False
    cont_batching:        bool = False
    no_webui:             bool = True
    extra_args:           list[str] = []
    auto_start:           bool = True
    auto_restart:         bool = False
    max_restart_attempts: int = 3
    startup_timeout:      int = 120


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def _build_cmd(config: dict) -> list[str]:
    """純函式：將 config dict 轉為 subprocess argv list（不用 shell）"""
    cmd = [
        config["executable_path"],
        "--model",   config["model_path"],
        "--host",    config["host"],
        "--port",    str(config["port"]),
        "--ctx-size", str(config["context_size"]),
        "--n-gpu-layers", str(config["n_gpu_layers"]),
        "--parallel", str(config.get("parallel", 1)),
        "--batch-size", str(config.get("batch_size", 512)),
    ]
    if config.get("n_threads") is not None:
        cmd += ["--threads", str(config["n_threads"])]
    if config.get("split_mode"):
        cmd += ["--split-mode", config["split_mode"]]
    if config.get("defrag_thold") is not None:
        cmd += ["--defrag-thold", str(config["defrag_thold"])]
    if config.get("cache_type_k"):
        cmd += ["--cache-type-k", config["cache_type_k"]]
    if config.get("cache_type_v"):
        cmd += ["--cache-type-v", config["cache_type_v"]]
    if config.get("flash_attn"):
        cmd += ["--flash-attn", "on"]
    if config.get("cont_batching"):
        cmd += ["--cont-batching"]
    if config.get("no_webui"):
        cmd += ["--no-webui"]
    cmd += list(config.get("extra_args") or [])
    return cmd


def _state_to_dict(state: InstanceState) -> dict:
    return {
        "name":                 state.name,
        "status":               state.status.value,
        "pid":                  state.pid,
        "started_at":           state.started_at,
        "restart_count":        state.restart_count,
        "config": {
            "executable_path":      state.config["executable_path"],
            "model_path":           state.config["model_path"],
            "host":                 state.config["host"],
            "port":                 state.config["port"],
            "context_size":         state.config["context_size"],
            "n_threads":            state.config.get("n_threads"),
            "n_gpu_layers":         state.config["n_gpu_layers"],
            "parallel":             state.config.get("parallel", 1),
            "batch_size":           state.config.get("batch_size", 512),
            "split_mode":           state.config.get("split_mode"),
            "defrag_thold":         state.config.get("defrag_thold"),
            "cache_type_k":         state.config.get("cache_type_k"),
            "cache_type_v":         state.config.get("cache_type_v"),
            "flash_attn":           bool(state.config.get("flash_attn")),
            "cont_batching":        bool(state.config.get("cont_batching")),
            "no_webui":             bool(state.config.get("no_webui")),
            "extra_args":           state.config.get("extra_args") or [],
            "auto_start":           bool(state.config["auto_start"]),
            "auto_restart":         bool(state.config["auto_restart"]),
            "max_restart_attempts": state.config["max_restart_attempts"],
            "startup_timeout":      state.config["startup_timeout"],
        },
    }


# ── Manager ───────────────────────────────────────────────────────────────────

class LlamaCppManager:
    def __init__(self):
        self._instances: dict[str, InstanceState] = {}
        self._lock = asyncio.Lock()

    # ── 啟動 ──────────────────────────────────────────────────────────────────

    async def startup(self):
        atexit.register(self._atexit_kill_all)

        def _load():
            db = get_db()
            try:
                rows = db.query(LlamaCppInstance).filter(LlamaCppInstance.is_active == 1).all()
                return [
                    {c.name: getattr(r, c.name) for c in LlamaCppInstance.__table__.columns}
                    for r in rows
                ]
            finally:
                db.close()

        rows = await asyncio.to_thread(_load)
        for cfg in rows:
            state = InstanceState(name=cfg["name"], config=cfg)
            self._instances[cfg["name"]] = state
            if cfg["auto_start"]:
                await self._start_instance(cfg["name"])

    def _atexit_kill_all(self):
        """同步保底：event loop 已停止時確保不留殭屍"""
        for state in self._instances.values():
            try:
                if state.proc and state.proc.returncode is None:
                    state.proc.kill()
            except Exception:
                pass

    # ── 關閉 ──────────────────────────────────────────────────────────────────

    async def shutdown(self):
        names = list(self._instances.keys())
        await asyncio.gather(
            *[self._stop_instance(n, remove=False) for n in names],
            return_exceptions=True,
        )

    # ── 啟動單一 instance ─────────────────────────────────────────────────────

    async def _start_instance(self, name: str):
        state = self._instances[name]
        state.status = InstanceStatus.STARTING
        state.restart_count = 0 if state.status != InstanceStatus.RESTARTING else state.restart_count

        kwargs = {}
        if sys.platform == "win32":
            import subprocess
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        cmd = _build_cmd(state.config)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **kwargs,
        )
        state.proc = proc
        state.pid = proc.pid
        state.started_at = datetime.now(TZ_LOCAL).isoformat()

        state.drain_task = asyncio.create_task(self._drain_stdout(state))
        state.monitor_task = asyncio.create_task(self._monitor(state))

    # ── 讀取 stdout（防 pipe buffer deadlock）────────────────────────────────

    async def _drain_stdout(self, state: InstanceState):
        try:
            while True:
                line = await state.proc.stdout.readline()
                if not line:
                    break
                state.log_buffer.append(line.decode("utf-8", errors="replace").rstrip())
        except Exception:
            pass

    # ── 監控 ─────────────────────────────────────────────────────────────────

    async def _monitor(self, state: InstanceState):
        cfg = state.config
        health_url = f"http://{cfg['host']}:{cfg['port']}/health"
        timeout = cfg["startup_timeout"]

        # Phase 1 — 等待就緒
        ready = False
        async with httpx.AsyncClient(timeout=2.0) as client:
            for _ in range(timeout):
                await asyncio.sleep(1)
                # process 已退出
                if state.proc.returncode is not None:
                    break
                try:
                    r = await client.get(health_url)
                    if r.status_code == 200:
                        ready = True
                        break
                except Exception:
                    pass

        if not ready:
            state.status = InstanceStatus.FAILED
            await self._force_kill(state)
            return

        state.status = InstanceStatus.RUNNING

        # Phase 2 — 穩定監控（每 30 秒）
        async with httpx.AsyncClient(timeout=5.0) as client:
            while True:
                await asyncio.sleep(30)
                # process 已退出
                if state.proc.returncode is not None:
                    break
                try:
                    r = await client.get(health_url)
                    if r.status_code != 200:
                        break
                except Exception:
                    break

        # process 退出或 HTTP 失敗
        if cfg["auto_restart"] and state.restart_count < cfg["max_restart_attempts"]:
            state.status = InstanceStatus.RESTARTING
            state.restart_count += 1
            delay = min(2 ** state.restart_count, 60)
            await asyncio.sleep(delay)
            if state.name in self._instances:
                await self._start_instance(state.name)
        else:
            state.status = InstanceStatus.FAILED

    # ── 強制終止 ──────────────────────────────────────────────────────────────

    async def _force_kill(self, state: InstanceState):
        if state.proc is None or state.proc.returncode is not None:
            return
        try:
            if sys.platform == "win32":
                tk = await asyncio.create_subprocess_exec(
                    "taskkill", "/F", "/T", "/PID", str(state.pid),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await tk.wait()
            else:
                state.proc.kill()
        except Exception:
            pass
        try:
            await asyncio.wait_for(state.proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

    # ── 停止單一 instance ─────────────────────────────────────────────────────

    async def _stop_instance(self, name: str, remove: bool = True):
        state = self._instances.get(name)
        if not state:
            return

        for task in (state.monitor_task, state.drain_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        await self._force_kill(state)
        state.status = InstanceStatus.STOPPED

        if remove:
            self._instances.pop(name, None)

    # ── 公開 CRUD 方法 ────────────────────────────────────────────────────────

    async def create_instance(self, req: InstanceCreateRequest) -> dict:
        async with self._lock:
            if req.name in self._instances:
                raise HTTPException(status_code=409, detail=f"Instance '{req.name}' already exists")

            now = datetime.now(TZ_LOCAL).isoformat()

            def _write():
                db = get_db()
                try:
                    row = LlamaCppInstance(
                        name=req.name,
                        executable_path=req.executable_path,
                        model_path=req.model_path,
                        host=req.host,
                        port=req.port,
                        context_size=req.context_size,
                        n_threads=req.n_threads,
                        n_gpu_layers=req.n_gpu_layers,
                        parallel=req.parallel,
                        batch_size=req.batch_size,
                        split_mode=req.split_mode,
                        defrag_thold=req.defrag_thold,
                        cache_type_k=req.cache_type_k,
                        cache_type_v=req.cache_type_v,
                        flash_attn=int(req.flash_attn),
                        cont_batching=int(req.cont_batching),
                        no_webui=int(req.no_webui),
                        extra_args=req.extra_args,
                        auto_start=int(req.auto_start),
                        auto_restart=int(req.auto_restart),
                        max_restart_attempts=req.max_restart_attempts,
                        startup_timeout=req.startup_timeout,
                        is_active=1,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(row)
                    db.commit()
                    return {c.name: getattr(row, c.name) for c in LlamaCppInstance.__table__.columns}
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

            cfg = await asyncio.to_thread(_write)
            state = InstanceState(name=req.name, config=cfg)
            self._instances[req.name] = state

            if req.auto_start:
                await self._start_instance(req.name)

            return _state_to_dict(state)

    def list_instances(self) -> list[dict]:
        return [_state_to_dict(s) for s in self._instances.values()]

    def get_instance(self, name: str) -> dict:
        state = self._instances.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
        return _state_to_dict(state)

    async def stop_instance(self, name: str) -> dict:
        if name not in self._instances:
            raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
        await self._stop_instance(name, remove=False)
        return _state_to_dict(self._instances[name])

    async def delete_instance(self, name: str):
        if name not in self._instances:
            raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
        await self._stop_instance(name, remove=True)

        def _delete():
            db = get_db()
            try:
                db.query(LlamaCppInstance).filter(LlamaCppInstance.name == name).delete(
                    synchronize_session=False
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        await asyncio.to_thread(_delete)

    async def restart_instance(self, name: str) -> dict:
        if name not in self._instances:
            raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
        await self._stop_instance(name, remove=False)
        state = self._instances[name]
        state.restart_count = 0
        await self._start_instance(name)
        return _state_to_dict(state)

    def get_logs(self, name: str, lines: int = 100) -> list[str]:
        state = self._instances.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
        buf = list(state.log_buffer)
        return buf[-lines:] if lines < len(buf) else buf


# ── APIRouter ─────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/llama", tags=["LLM Instances"])


def _manager(request: Request) -> LlamaCppManager:
    return request.app.state.llama_manager


@router.post("/instances", status_code=201)
async def create_instance(body: InstanceCreateRequest, request: Request):
    """建立一個新的 llama.cpp 實例"""
    return await _manager(request).create_instance(body)


@router.get("/instances")
def list_instances(request: Request):
    """列出所有 llama.cpp 實例"""
    return _manager(request).list_instances()


@router.get("/instances/{name}")
def get_instance(name: str, request: Request):
    """取得特定 llama.cpp 實例的狀態"""
    return _manager(request).get_instance(name)


@router.delete("/instances/{name}", status_code=204)
async def delete_instance(name: str, request: Request):
    """刪除一個 llama.cpp 實例"""
    await _manager(request).delete_instance(name)


@router.post("/instances/{name}/stop")
async def stop_instance(name: str, request: Request):
    """停止一個 llama.cpp 實例"""
    return await _manager(request).stop_instance(name)


@router.post("/instances/{name}/restart")
async def restart_instance(name: str, request: Request):
    """重新啟動一個 llama.cpp 實例"""
    return await _manager(request).restart_instance(name)


@router.get("/instances/{name}/logs")
def get_logs(name: str, request: Request, lines: int = 100):
    """取得 llama.cpp 實例的日誌"""
    return _manager(request).get_logs(name, lines)
