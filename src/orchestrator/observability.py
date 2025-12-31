"""
Unified hardware/software observability for DGX Spark (Grace Blackwell).

Exposes a single pulse metric for unified memory and core affinity.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Literal, Tuple, List

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

from ..shared.config import MAX_KV_CACHE_GB
from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Prefer nvidia-ml-py; fall back to pynvml for compatibility
try:
    import nvidia_smi as pynvml  # type: ignore
except Exception:  # noqa: BLE001
    try:
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
        import pynvml  # type: ignore
    except Exception:  # pragma: no cover
        pynvml = None

if pynvml:
    try:
        pynvml.nvmlInit()
        _nvml_available = True
    except Exception:  # pragma: no cover
        _nvml_available = False
        logger.warning("pynvml initialization failed; GPU stats will be omitted")
else:  # pragma: no cover
    _nvml_available = False
    logger.warning("pynvml not available; GPU stats will be omitted")


PERFORMANCE_CORES = set(range(10, 20))  # X925
EFFICIENCY_CORES = set(range(0, 10))  # A725


def _collect_unified_memory() -> Tuple[float, float]:
    """Return (used_gb, total_gb) for unified memory pool via psutil."""
    if psutil is None:  # pragma: no cover
        return 0.0, 1.0
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    return used_gb, total_gb


def _kv_cache_reserved_gb() -> float:
    try:
        return float(MAX_KV_CACHE_GB)
    except Exception:
        return 0.0


def _gpu_usage_gb() -> Optional[float]:
    if not _nvml_available:
        return None
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return mem.used / (1024 ** 3)
    except Exception:
        return None


def _process_affinity_labels() -> str:
    """Inspect cortex-* processes and infer active core class."""
    labels: List[str] = []
    if psutil is None:
        return "idle"
    for proc in psutil.process_iter(["name", "pid", "cmdline", "cpu_affinity"]):
        try:
            name = proc.info.get("name") or ""
            cmd = " ".join(proc.info.get("cmdline") or [])
            if "cortex-brain" in name or "cortex-worker" in name or "cortex-brain" in cmd or "cortex-worker" in cmd:
                affinity = set(proc.cpu_affinity())
                if affinity and affinity.issubset(PERFORMANCE_CORES):
                    labels.append("performance")
                elif affinity and affinity.issubset(EFFICIENCY_CORES):
                    labels.append("efficiency")
                else:
                    labels.append("hybrid")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception as exc:
            logger.debug("Affinity check failed", extra={"payload": {"error": str(exc)}})
            continue

    if not labels:
        return "idle"
    if all(l == "performance" for l in labels):
        return "performance"
    if all(l == "efficiency" for l in labels):
        return "efficiency"
    return "hybrid"


def get_system_pulse() -> Dict[str, float | str]:
    """Compute unified memory pressure and core affinity."""
    used_gb, total_gb = _collect_unified_memory()
    kv_reserved = _kv_cache_reserved_gb()
    gpu_extra = _gpu_usage_gb() or 0.0

    unified_used = used_gb + kv_reserved
    memory_pressure = (unified_used / total_gb) * 100 if total_gb else 0.0

    return {
        "memory_pressure": round(memory_pressure, 1),
        "unified_usage_gb": round(unified_used, 1),
        "unified_total_gb": round(total_gb, 1),
        "kv_reserved_gb": round(kv_reserved, 1),
        "gpu_used_gb": round(gpu_extra, 1) if gpu_extra else 0.0,
        "active_cores": _process_affinity_labels(),
    }
