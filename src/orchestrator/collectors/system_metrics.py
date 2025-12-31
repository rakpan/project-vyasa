"""
System metrics fallback for GPU/UMA telemetry.

Uses nvidia-ml-py (nvidia_smi) when available; falls back to nvidia-smi subprocess.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

GB10_TOTAL_VRAM_GB = 128.0

try:
    import nvidia_smi  # type: ignore

    _has_nvidia_smi = True
    nvidia_smi.nvmlInit()
except Exception:  # pragma: no cover - optional dependency
    _has_nvidia_smi = False

try:
    import psutil  # type: ignore

    _has_psutil = True
except Exception:  # pragma: no cover - optional dependency
    _has_psutil = False


class SystemMetricsCollector:
    """Collect GPU/UMA metrics with lightweight fallbacks."""

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout

    def _collect_with_nvml(self) -> Optional[Dict[str, float]]:
        try:
            device = nvidia_smi.nvmlDeviceGetHandleByIndex(0)
            util = nvidia_smi.nvmlDeviceGetUtilizationRates(device)
            mem = nvidia_smi.nvmlDeviceGetMemoryInfo(device)
            gpu_util = float(util.gpu)
            used_gb = float(mem.used) / (1024 ** 3)
            total_gb = float(mem.total) / (1024 ** 3)
            return {
                "gpu_utilization_pct": gpu_util,
                "vram_used_gb": round(used_gb, 2),
                "total_vram_gb": round(total_gb, 2),
            }
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning("NVML collection failed", extra={"payload": {"error": str(exc)}})
            return None

    def _collect_with_nvidia_smi(self) -> Optional[Dict[str, float]]:
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ]
            output = subprocess.check_output(cmd, timeout=self.timeout, text=True).strip()
            if not output:
                return None
            # Use first GPU line
            line = output.splitlines()[0]
            util_str, used_str, total_str = [token.strip() for token in line.split(",")]
            gpu_util = float(util_str)
            used_gb = float(used_str) / 1024 if float(total_str) > 200000 else float(used_str)
            total_gb = float(total_str) / 1024 if float(total_str) > 200000 else float(total_str)
            return {
                "gpu_utilization_pct": gpu_util,
                "vram_used_gb": round(used_gb, 2),
                "total_vram_gb": round(total_gb, 2),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("nvidia-smi collection failed", extra={"payload": {"error": str(exc)}})
            return None

    def collect(self) -> Dict[str, Any]:
        """Return normalized hardware panel fields."""
        snapshot: Optional[Dict[str, float]] = None
        if _has_nvidia_smi:
            snapshot = self._collect_with_nvml()
        if snapshot is None:
            snapshot = self._collect_with_nvidia_smi()

        if snapshot is None:
            return {
                "hardware": {
                    "uma_utilization_pct": None,
                    "gpu_utilization_pct": None,
                    "vram_used_gb": None,
                    "total_vram_gb": GB10_TOTAL_VRAM_GB,
                }
            }

        vram_used = snapshot["vram_used_gb"]
        total_vram = snapshot["total_vram_gb"] or GB10_TOTAL_VRAM_GB

        # Unified pool: system RAM + VRAM, capped at platform limit (128GB)
        system_used_gb = 0.0
        system_total_gb = 0.0
        if _has_psutil:
            try:
                mem = psutil.virtual_memory()
                system_used_gb = float(mem.used) / (1024 ** 3)
                system_total_gb = float(mem.total) / (1024 ** 3)
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug("psutil memory read failed", extra={"payload": {"error": str(exc)}})

        unified_used = vram_used + system_used_gb
        unified_total = GB10_TOTAL_VRAM_GB  # DGX Spark unified pool target
        if total_vram and system_total_gb:
            unified_total = min(GB10_TOTAL_VRAM_GB, total_vram + system_total_gb)
        uma_utilization_pct = round((unified_used / unified_total) * 100, 2) if unified_total else None

        return {
            "hardware": {
                "uma_utilization_pct": uma_utilization_pct,
                "gpu_utilization_pct": snapshot["gpu_utilization_pct"],
                "vram_used_gb": snapshot["vram_used_gb"],
                "total_vram_gb": total_vram,
            }
        }
