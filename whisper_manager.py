import asyncio
import sys
import shutil
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from db import get_db, WhisperCluster, WhisperTranscriptionJob, UsageLog, ApiKey

TZ_LOCAL = timezone(timedelta(hours=8))

WHISPER_MODEL_NAME = "whisper-1"


# ── 音訊格式工具 ──────────────────────────────────────────────────────────────

def _is_wav(data: bytes) -> bool:
    """偵測是否為 WAV 格式（magic bytes: RIFF....WAVE）"""
    return len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE'


async def _ensure_wav_16k(audio_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """
    若音訊已是 WAV 則直接回傳。
    否則用 ffmpeg 轉為 16000Hz mono 16-bit PCM WAV。
    """
    if _is_wav(audio_bytes):
        return audio_bytes, filename

    if shutil.which("ffmpeg") is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "收到非 WAV 音訊，但 ffmpeg 未安裝或不在 PATH 中。"
                "請安裝 ffmpeg 或先手動轉換為 WAV（16kHz, mono, 16-bit PCM）。"
            ),
        )

    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-ar", "16000",
        "-ac", "1",
        "-sample_fmt", "s16",
        "-f", "wav",
        "pipe:1",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        wav_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=audio_bytes),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ffmpeg 音訊轉換逾時（超過 120 秒）")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="ffmpeg 執行失敗，請確認安裝正確")

    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace")[:300]
        raise HTTPException(
            status_code=422,
            detail=f"ffmpeg 無法轉換音訊（exit {proc.returncode}）: {err_msg}",
        )

    if not wav_bytes:
        raise HTTPException(status_code=422, detail="ffmpeg 轉換結果為空，音訊可能損壞")

    stem = Path(filename).stem
    return wav_bytes, f"{stem}.wav"


def _wav_duration_ms(wav_bytes: bytes) -> int | None:
    """從 WAV 檔掃描 chunk 取得音訊長度（ms），支援 ffmpeg 輸出的非標準佈局。"""
    import struct
    try:
        if len(wav_bytes) < 44 or wav_bytes[:4] != b'RIFF' or wav_bytes[8:12] != b'WAVE':
            return None
        # 從 fmt chunk 取得音訊參數
        num_channels = sample_rate = bits_per_sample = None
        pos = 12
        data_size = None
        while pos + 8 <= len(wav_bytes):
            chunk_id = wav_bytes[pos:pos+4]
            chunk_size = struct.unpack_from('<I', wav_bytes, pos+4)[0]
            if chunk_id == b'fmt ':
                if chunk_size >= 16:
                    num_channels    = struct.unpack_from('<H', wav_bytes, pos+10)[0]
                    sample_rate     = struct.unpack_from('<I', wav_bytes, pos+12)[0]
                    bits_per_sample = struct.unpack_from('<H', wav_bytes, pos+22)[0]
            elif chunk_id == b'data':
                data_size = chunk_size
                break
            pos += 8 + chunk_size
            if chunk_size % 2:  # WAV chunks 對齊到偶數位元組
                pos += 1
        if None in (num_channels, sample_rate, bits_per_sample, data_size):
            return None
        if sample_rate == 0 or bits_per_sample == 0 or num_channels == 0:
            return None
        bytes_per_sample = bits_per_sample // 8
        total_samples = data_size // (num_channels * bytes_per_sample)
        return int(total_samples / sample_rate * 1000)
    except Exception:
        return None


# ── 資料結構 ──────────────────────────────────────────────────────────────────

# whisper-cli 診斷雜訊行前綴
_NOISE_PREFIXES = (
    "whisper_", "ggml_", "main:", "system_info",
    "log_mel_spectrogram", "output_txt", "output_srt",
)


def _is_segment_line(line: str) -> bool:
    """判斷是否為有效的 segment 輸出行（非診斷雜訊）"""
    stripped = line.strip()
    if not stripped:
        return False
    if any(stripped.startswith(p) for p in _NOISE_PREFIXES):
        return False
    return True


@dataclass
class WhisperClusterState:
    name:          str
    config:        dict
    max_instances: int
    is_default:    bool
    log_buffer:    deque = field(default_factory=lambda: deque(maxlen=500))
    _active_count: int = field(default=0, repr=False)
    _lock:         asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


# ── Pydantic Models ───────────────────────────────────────────────────────────

class WhisperClusterCreateRequest(BaseModel):
    name:           str
    executable_path: str
    model_path:     str
    n_threads:      Optional[int] = None
    n_processors:   Optional[int] = None
    beam_size:      Optional[int] = None
    best_of:        Optional[int] = None
    audio_ctx:      Optional[int] = None
    max_instances:  int = 2
    is_default:     bool = False


class WhisperClusterUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    executable_path: Optional[str] = None
    model_path:      Optional[str] = None
    n_threads:       Optional[int] = None
    n_processors:    Optional[int] = None
    beam_size:       Optional[int] = None
    best_of:         Optional[int] = None
    audio_ctx:       Optional[int] = None
    max_instances:   Optional[int] = None
    is_default:      Optional[bool] = None


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def _build_cli_cmd(config: dict, wav_path: str, params: dict) -> list[str]:
    """將 cluster config + 請求參數轉為 whisper-cli argv list"""
    cmd = [
        config["executable_path"],
        "--model", config["model_path"],
        "--file",  wav_path,
    ]
    if config.get("n_threads") is not None:
        cmd += ["--threads", str(config["n_threads"])]
    if config.get("n_processors") is not None:
        cmd += ["--processors", str(config["n_processors"])]
    if config.get("beam_size") is not None:
        cmd += ["--beam-size", str(config["beam_size"])]
    if config.get("best_of") is not None:
        cmd += ["--best-of", str(config["best_of"])]
    if config.get("audio_ctx") is not None:
        cmd += ["--audio-ctx", str(config["audio_ctx"])]
    if params.get("language"):
        cmd += ["--language", params["language"]]
    if params.get("prompt"):
        cmd += ["--prompt", params["prompt"]]
    if params.get("temperature") is not None:
        cmd += ["--temperature", str(params["temperature"])]
    return cmd


def _cluster_to_dict(state: WhisperClusterState) -> dict:
    return {
        "name":         state.name,
        "status":       "running" if state._active_count > 0 else "stopped",
        "active_count": state._active_count,
        "config": {
            "executable_path": state.config["executable_path"],
            "model_path":      state.config["model_path"],
            "n_threads":       state.config.get("n_threads"),
            "n_processors":    state.config.get("n_processors"),
            "beam_size":       state.config.get("beam_size"),
            "best_of":         state.config.get("best_of"),
            "audio_ctx":       state.config.get("audio_ctx"),
            "max_instances":   state.max_instances,
            "is_default":      state.is_default,
        },
    }


def _mark_job_status(job_id: int, status: str, error_message: str | None = None):
    db = get_db()
    try:
        row = db.query(WhisperTranscriptionJob).filter(
            WhisperTranscriptionJob.id == job_id
        ).first()
        if row:
            row.status = status
            if error_message:
                row.error_message = error_message
            row.completed_at = datetime.now(TZ_LOCAL).isoformat()
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ── Manager ───────────────────────────────────────────────────────────────────

class WhisperCppManager:
    def __init__(self):
        self._clusters: dict[str, WhisperClusterState] = {}
        self._lock = asyncio.Lock()
        self._active_procs: set[asyncio.subprocess.Process] = set()

    # ── 啟動 / 關閉 ───────────────────────────────────────────────────────────

    async def startup(self):
        def _load():
            db = get_db()
            try:
                rows = db.query(WhisperCluster).filter(WhisperCluster.is_active == 1).all()
                return [
                    {c.name: getattr(r, c.name) for c in WhisperCluster.__table__.columns}
                    for r in rows
                ]
            finally:
                db.close()

        rows = await asyncio.to_thread(_load)
        for cfg in rows:
            state = WhisperClusterState(
                name=cfg["name"],
                config=cfg,
                max_instances=cfg["max_instances"],
                is_default=bool(cfg["is_default"]),
            )
            self._clusters[cfg["name"]] = state

    async def shutdown(self):
        """主動 kill 所有正在跑的 whisper-cli"""
        procs = list(self._active_procs)
        for proc in procs:
            try:
                if proc.returncode is None:
                    proc.kill()
            except Exception:
                pass
        if procs:
            await asyncio.wait(
                [asyncio.create_task(proc.wait()) for proc in procs],
                timeout=5.0,
            )

    # ── 核心轉錄 ──────────────────────────────────────────────────────────────

    def _get_cluster(self, name: str | None) -> WhisperClusterState:
        if name:
            c = self._clusters.get(name)
            if not c:
                raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found")
            return c
        for c in self._clusters.values():
            if c.is_default:
                return c
        raise HTTPException(
            status_code=503,
            detail="沒有可用的預設 Whisper Cluster，請先建立並設為預設"
        )

    async def transcribe_stream(
        self,
        audio_bytes: bytes,
        filename: str,
        params: dict,
        cluster_name: str | None = None,
        api_key: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        執行轉錄，每個 confirmed segment（整行 \\n）yield 一次原始輸出。
        超過 max_instances → 429。client 中斷 → CancelledError → kill subprocess。
        """
        cluster = self._get_cluster(cluster_name)

        # 並發控制：原子性 check-and-increment
        async with cluster._lock:
            if cluster._active_count >= cluster.max_instances:
                raise HTTPException(
                    status_code=429,
                    detail=f"Cluster '{cluster.name}' 已達最大並發數 {cluster.max_instances}，請稍後再試",
                )
            cluster._active_count += 1

        now = datetime.now(TZ_LOCAL).isoformat()

        def _create_job():
            db = get_db()
            try:
                row = WhisperTranscriptionJob(
                    cluster_name=cluster.name,
                    filename=filename or "audio",
                    status="pending",
                    response_format=params.get("response_format", "json"),
                    created_at=now,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return row.id
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        job_id = await asyncio.to_thread(_create_job)
        t_start = time.monotonic()
        tmp_path = None
        proc = None

        try:
            audio_bytes, wav_filename = await _ensure_wav_16k(audio_bytes, filename)
            duration_ms = _wav_duration_ms(audio_bytes)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            def _mark_processing():
                db = get_db()
                try:
                    row = db.query(WhisperTranscriptionJob).filter(
                        WhisperTranscriptionJob.id == job_id
                    ).first()
                    if row:
                        row.status = "processing"
                        db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()

            await asyncio.to_thread(_mark_processing)

            kwargs: dict = {}
            if sys.platform == "win32":
                import subprocess as _sp
                kwargs["creationflags"] = _sp.CREATE_NO_WINDOW

            cmd = _build_cli_cmd(cluster.config, tmp_path, params)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **kwargs,
            )
            self._active_procs.add(proc)

            try:
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if _is_segment_line(line):
                        yield line
            except (asyncio.CancelledError, GeneratorExit):
                proc.kill()
                _mark_job_status(job_id, "failed", "客戶端中斷連線")
                raise

            await proc.wait()

            if proc.returncode != 0:
                stderr_out = (await proc.stderr.read()).decode(errors="replace")[:200]
                await asyncio.to_thread(_mark_job_status, job_id, "failed", stderr_out)
                raise HTTPException(
                    status_code=502,
                    detail=f"whisper-cli 失敗 (exit {proc.returncode}): {stderr_out}",
                )

            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            completed_at = datetime.now(TZ_LOCAL).isoformat()

            def _mark_done():
                db = get_db()
                try:
                    row = db.query(WhisperTranscriptionJob).filter(
                        WhisperTranscriptionJob.id == job_id
                    ).first()
                    if row:
                        row.status = "done"
                        row.processing_time_ms = elapsed_ms
                        row.audio_duration_ms = duration_ms
                        row.completed_at = completed_at
                    # 寫入 UsageLog
                    log = UsageLog(
                        api_key=api_key or "",
                        model=WHISPER_MODEL_NAME,
                        request_type="audio",
                        date=datetime.now(TZ_LOCAL).strftime("%Y-%m-%d"),
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        cost_usd=0.0,
                        audio_duration_ms=duration_ms,
                        created_at=completed_at,
                    )
                    db.add(log)
                    # 更新 ApiKey 累計 request 數
                    if api_key:
                        key_row = db.query(ApiKey).filter(ApiKey.key == api_key).first()
                        if key_row:
                            key_row.total_requests += 1
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()

            await asyncio.to_thread(_mark_done)

        finally:
            async with cluster._lock:
                cluster._active_count -= 1
            if proc is not None:
                self._active_procs.discard(proc)
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
            # 確保非正常結束時 job 狀態不會卡在 pending/processing
            def _ensure_terminal_status():
                db = get_db()
                try:
                    row = db.query(WhisperTranscriptionJob).filter(
                        WhisperTranscriptionJob.id == job_id,
                        WhisperTranscriptionJob.status.in_(["pending", "processing"]),
                    ).first()
                    if row:
                        row.status = "failed"
                        row.completed_at = datetime.now(TZ_LOCAL).isoformat()
                        db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()
            await asyncio.to_thread(_ensure_terminal_status)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        params: dict,
        cluster_name: str | None = None,
        api_key: str | None = None,
    ) -> dict:
        """非串流版：等轉錄完成，回傳完整結果"""
        segments: list[str] = []
        async for line in self.transcribe_stream(audio_bytes, filename, params, cluster_name, api_key):
            segments.append(line)
        return {"text": "\n".join(segments)}

    # ── 轉錄歷史 ──────────────────────────────────────────────────────────────

    async def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        def _query():
            db = get_db()
            try:
                rows = (
                    db.query(WhisperTranscriptionJob)
                    .order_by(WhisperTranscriptionJob.id.desc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                return [
                    {c.name: getattr(r, c.name) for c in WhisperTranscriptionJob.__table__.columns}
                    for r in rows
                ]
            finally:
                db.close()

        return await asyncio.to_thread(_query)

    # ── 公開 CRUD 方法 ────────────────────────────────────────────────────────

    async def create_cluster(self, req: WhisperClusterCreateRequest) -> dict:
        async with self._lock:
            if req.name in self._clusters:
                raise HTTPException(status_code=409, detail=f"Cluster '{req.name}' already exists")

            now = datetime.now(TZ_LOCAL).isoformat()

            def _write():
                db = get_db()
                try:
                    # 若設為預設，先清除其他 cluster 的 is_default
                    if req.is_default:
                        db.query(WhisperCluster).update({"is_default": 0})
                    row = WhisperCluster(
                        name=req.name,
                        executable_path=req.executable_path,
                        model_path=req.model_path,
                        n_threads=req.n_threads,
                        n_processors=req.n_processors,
                        beam_size=req.beam_size,
                        best_of=req.best_of,
                        audio_ctx=req.audio_ctx,
                        max_instances=req.max_instances,
                        is_default=int(req.is_default),
                        is_active=1,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(row)
                    db.commit()
                    return {c.name: getattr(row, c.name) for c in WhisperCluster.__table__.columns}
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

            cfg = await asyncio.to_thread(_write)

            # 若設為預設，同步更新記憶體中其他 cluster
            if req.is_default:
                for s in self._clusters.values():
                    s.is_default = False

            state = WhisperClusterState(
                name=req.name,
                config=cfg,
                max_instances=req.max_instances,
                is_default=req.is_default,
            )
            self._clusters[req.name] = state
            return _cluster_to_dict(state)

    def list_clusters(self) -> list[dict]:
        return [_cluster_to_dict(s) for s in self._clusters.values()]

    def get_cluster_info(self, name: str) -> dict:
        state = self._clusters.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found")
        return _cluster_to_dict(state)

    async def delete_cluster(self, name: str):
        if name not in self._clusters:
            raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found")

        async with self._lock:
            self._clusters.pop(name)

        def _delete():
            db = get_db()
            try:
                db.query(WhisperCluster).filter(WhisperCluster.name == name).delete(
                    synchronize_session=False
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        await asyncio.to_thread(_delete)

    async def update_cluster(self, name: str, req: WhisperClusterUpdateRequest) -> dict:
        async with self._lock:
            if name not in self._clusters:
                raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found")
            state = self._clusters[name]
            now = datetime.now(TZ_LOCAL).isoformat()
            fields = req.model_fields_set
            setting_default = "is_default" in fields and req.is_default

            def _write():
                db = get_db()
                try:
                    if setting_default:
                        db.query(WhisperCluster).update({"is_default": 0})
                    row = db.query(WhisperCluster).filter(WhisperCluster.name == name).first()
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found in DB")
                    for field_name in fields:
                        val = getattr(req, field_name)
                        if field_name == "is_default":
                            val = int(val)
                        setattr(row, field_name, val)
                    row.updated_at = now
                    db.commit()
                    return {c.name: getattr(row, c.name) for c in WhisperCluster.__table__.columns}
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

            cfg = await asyncio.to_thread(_write)

            if setting_default:
                for s in self._clusters.values():
                    s.is_default = False

            for k in fields:
                if k == "max_instances":
                    state.max_instances = cfg["max_instances"]
                elif k == "is_default":
                    state.is_default = bool(cfg["is_default"])
                else:
                    state.config[k] = cfg[k]

        return _cluster_to_dict(state)

    def get_logs(self, name: str, lines: int = 100) -> list[str]:
        state = self._clusters.get(name)
        if not state:
            raise HTTPException(status_code=404, detail=f"Cluster '{name}' not found")
        buf = list(state.log_buffer)
        return buf[-lines:] if lines < len(buf) else buf


# ── APIRouter ─────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/whisper", tags=["Whisper Clusters"])


def _manager(request: Request) -> WhisperCppManager:
    return request.app.state.whisper_manager


@router.post("/clusters", status_code=201)
async def create_cluster(body: WhisperClusterCreateRequest, request: Request):
    """建立一個新的 Whisper Cluster"""
    try:
        return await _manager(request).create_cluster(body)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create cluster: {str(e)}")


@router.get("/clusters")
def list_clusters(request: Request):
    """列出所有 Whisper Cluster（含即時 active_count）"""
    return _manager(request).list_clusters()


@router.get("/clusters/{name}")
def get_cluster(name: str, request: Request):
    """取得特定 Whisper Cluster 的狀態"""
    return _manager(request).get_cluster_info(name)


@router.delete("/clusters/{name}", status_code=204)
async def delete_cluster(name: str, request: Request):
    """刪除一個 Whisper Cluster"""
    await _manager(request).delete_cluster(name)


@router.patch("/clusters/{name}")
async def update_cluster(name: str, body: WhisperClusterUpdateRequest, request: Request):
    """更新 Whisper Cluster 設定"""
    try:
        return await _manager(request).update_cluster(name, body)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update cluster: {str(e)}")


@router.get("/clusters/{name}/logs")
def get_logs(name: str, request: Request, lines: int = 100):
    """取得 Cluster 的日誌緩衝"""
    return _manager(request).get_logs(name, lines)


@router.get("/jobs")
async def list_jobs(request: Request, limit: int = 50, offset: int = 0):
    """取得轉錄歷史記錄"""
    return await _manager(request).list_jobs(limit=limit, offset=offset)
