"""Hardware acceleration detection for FFmpeg."""

import logging
import shutil
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# GPU Encoders definition
GPU_DRIVERS = {
    "nvenc": {
        "label": "NVIDIA NVENC",
        "h264": "h264_nvenc",
        "hevc": "hevc_nvenc",
        "hwaccel": ["-hwaccel", "cuda"]
    },
    "qsv": {
        "label": "Intel Quick Sync (QSV)",
        "h264": "h264_qsv",
        "hevc": "hevc_qsv",
        "hwaccel": ["-hwaccel", "qsv"]
    },
    "vaapi": {
        "label": "Linux VA-API",
        "h264": "h264_vaapi",
        "hevc": "hevc_vaapi",
        "hwaccel": ["-hwaccel", "vaapi", "-hwaccel_device", "/dev/dri/renderD128"]
    },
    "amf": {
        "label": "AMD AMF",
        "h264": "h264_amf",
        "hevc": "hevc_amf",
        "hwaccel": []
    }
}

_cached_gpu_info: Optional[Dict[str, str]] = None


def detect_gpu_encoder() -> Dict[str, str]:
    """Detect available working hardware encoder on the system.
    
    Returns:
        Dict with keys: name, label, h264, hevc, or empty dict if none.
    """
    global _cached_gpu_info
    if _cached_gpu_info is not None:
        return _cached_gpu_info

    if not shutil.which("ffmpeg"):
        _cached_gpu_info = {}
        return _cached_gpu_info

    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=8
        )
        encoders_str = res.stdout if res.returncode == 0 else ""
    except Exception as e:
        logger.debug("FFmpeg encoder check error: %s", e)
        _cached_gpu_info = {}
        return _cached_gpu_info

    for name, info in GPU_DRIVERS.items():
        h264_enc = info["h264"]
        if h264_enc in encoders_str:
            # Test that the encoder actually works with current hardware/drivers
            try:
                test_res = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.2",
                        "-c:v", h264_enc, "-frames:v", "1",
                        "-f", "null", "-"
                    ],
                    capture_output=True,
                    timeout=5
                )
                if test_res.returncode == 0:
                    logger.info("Found working GPU encoder: %s (%s)", info["label"], name)
                    _cached_gpu_info = {
                        "name": name,
                        "label": info["label"],
                        "h264": info["h264"],
                        "hevc": info["hevc"],
                    }
                    return _cached_gpu_info
            except Exception:
                continue

    _cached_gpu_info = {}
    return _cached_gpu_info
