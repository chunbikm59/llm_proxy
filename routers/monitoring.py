"""系統監控路由"""
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter

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
