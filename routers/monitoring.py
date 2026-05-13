"""系統監控路由"""
import asyncio
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Request
import httpx

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

import psutil
import threading
import subprocess as _sp

TZ_LOCAL = timezone(timedelta(hours=8))

router = APIRouter(tags=["Monitoring"])

_cpu_cache: dict = {'value': 0.0}


def _get_cpu_utility() -> float:
    """取得與工作管理員一致的 CPU 使用率（% Processor Utility，頻率加權）"""
    try:
        r = _sp.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-Counter "\\Processor Information(_Total)\\% Processor Utility").CounterSamples.CookedValue'],
            capture_output=True, text=True, timeout=4
        )
        return round(float(r.stdout.strip()), 1)
    except Exception:
        return psutil.cpu_percent(interval=None)


def _cpu_poller():
    """背景執行緒，每 2 秒更新一次 CPU 使用率快取"""
    psutil.cpu_percent(interval=None)
    while True:
        _cpu_cache['value'] = _get_cpu_utility()
        threading.Event().wait(2)


# 啟動背景 CPU 輪詢執行緒
threading.Thread(target=_cpu_poller, daemon=True).start()


@router.get("/admin/system/stats")
async def system_stats():
    """取得系統資源使用統計"""
    def _collect():
        cpu_percent = _cpu_cache['value']
        vm = psutil.virtual_memory()
        gpus = []
        if _NVML_AVAILABLE:
            try:
                for i in range(pynvml.nvmlDeviceGetCount()):
                    h = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    util = pynvml.nvmlDeviceGetUtilizationRates(h)
                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                    except Exception:
                        temp = None
                    name = pynvml.nvmlDeviceGetName(h)
                    if isinstance(name, bytes):
                        name = name.decode('utf-8')
                    gpus.append({
                        "index": i,
                        "name": name,
                        "util_percent": float(util.gpu),
                        "vram_used_gb": round(mem.used / 1024**3, 1),
                        "vram_total_gb": round(mem.total / 1024**3, 1),
                        "vram_percent": round(mem.used / mem.total * 100, 1) if mem.total else 0.0,
                        "temperature_c": temp,
                    })
            except Exception:
                pass
        return {
            "cpu": {
                "percent": cpu_percent,
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
            },
            "ram": {
                "percent": round(vm.percent, 1),
                "used_gb": round(vm.used / 1024**3, 1),
                "total_gb": round(vm.total / 1024**3, 1),
            },
            "gpu": gpus,
            "gpu_available": _NVML_AVAILABLE and len(gpus) > 0,
            "timestamp": datetime.now(TZ_LOCAL).isoformat(),
        }
    return await asyncio.to_thread(_collect)


@router.get("/admin/llama/slots")
async def get_llama_slots(request: Request):
    """查詢每個 llama.cpp server 的 slot 推論狀態，並附上 proxy 層的 in-flight 計數"""
    manager = request.app.state.llama_manager
    in_flight: dict[str, int] = request.app.state.in_flight
    instances = manager.list_instances()
    results = []
    async with httpx.AsyncClient(timeout=1.5) as client:
        for inst in instances:
            if inst["status"] != "running":
                results.append({
                    "name": inst["name"],
                    "host": inst["config"]["host"],
                    "port": inst["config"]["port"],
                    "status": inst["status"],
                    "slots": None,
                    "slot_details": [],
                    "in_flight": 0,
                    "error": None,
                })
                continue
            host = inst["config"]["host"]
            port = inst["config"]["port"]
            try:
                resp = await client.get(f"http://{host}:{port}/slots")
                resp.raise_for_status()
                raw_slots = resp.json()
                processing = sum(1 for s in raw_slots if s.get("is_processing") or s.get("state") == 1)
                idle = len(raw_slots) - processing
                inst_in_flight = _sum_in_flight_for_port(in_flight, port)
                slot_details = []
                for s in raw_slots:
                    params = s.get("params") or {}
                    next_token = (s.get("next_token") or [{}])
                    nt = next_token[0] if next_token else {}
                    slot_details.append({
                        "id": s.get("id"),
                        "is_processing": bool(s.get("is_processing") or s.get("state") == 1),
                        "prompt": (s.get("prompt") or "")[:200],
                        "n_decoded": nt.get("n_decoded"),
                        "n_remain": nt.get("n_remain"),
                        "n_prompt_tokens": s.get("n_prompt_tokens"),
                        "temperature": params.get("temperature"),
                        "top_p": params.get("top_p"),
                        "seed": params.get("seed"),
                        "model": s.get("model"),
                    })
                results.append({
                    "name": inst["name"],
                    "host": host,
                    "port": port,
                    "status": inst["status"],
                    "slots": {
                        "total": len(raw_slots),
                        "processing": processing,
                        "idle": idle,
                    },
                    "slot_details": slot_details,
                    "in_flight": inst_in_flight,
                    "error": None,
                })
            except Exception as e:
                results.append({
                    "name": inst["name"],
                    "host": host,
                    "port": port,
                    "status": inst["status"],
                    "slots": None,
                    "slot_details": [],
                    "in_flight": 0,
                    "error": str(e),
                })
    return {"instances": results, "in_flight": in_flight}


def _build_port_to_models() -> dict[int, list[str]]:
    """解析 litellm_config.yaml，建立 port → [model_name] 的對應表"""
    config_path = Path(__file__).parent.parent / "litellm_config.yaml"
    mapping: dict[int, list[str]] = {}
    try:
        text = config_path.read_text(encoding="utf-8")
        blocks = re.split(r'\n  - model_name:', text)
        for block in blocks[1:]:
            name_m = re.match(r'\s*(\S+)', block)
            port_m = re.search(r'api_base:\s*http://[^:]+:(\d+)', block)
            if name_m and port_m:
                model_name = name_m.group(1)
                port = int(port_m.group(1))
                mapping.setdefault(port, []).append(model_name)
    except Exception:
        pass
    return mapping


def _sum_in_flight_for_port(in_flight: dict, port: int) -> int:
    """查詢指定 port 的 llama instance 在 proxy 層有多少進行中請求"""
    port_to_models = _build_port_to_models()
    model_names = port_to_models.get(port, [])
    if model_names:
        return sum(in_flight.get(m, 0) for m in model_names)
    return sum(in_flight.values())
