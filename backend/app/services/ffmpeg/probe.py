"""Media file probing using ffprobe."""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def is_ffprobe_available() -> bool:
    """Check if ffprobe is installed and on system PATH."""
    return shutil.which("ffprobe") is not None


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is installed and on system PATH."""
    return shutil.which("ffmpeg") is not None


def format_duration(seconds: Optional[float]) -> str:
    """Format seconds into HH:MM:SS or MM:SS string."""
    if seconds is None or seconds < 0:
        return "Unknown"
    secs = int(seconds)
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    rem_secs = secs % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{rem_secs:02d}"
    return f"{minutes:02d}:{rem_secs:02d}"


def format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def probe_file(file_path: Path) -> Dict[str, Any]:
    """Execute ffprobe and return parsed metadata dictionary.
    
    Args:
        file_path: Path to the media file.
        
    Returns:
        Dictionary containing metadata (duration, resolution, codecs, bitrates).
    """
    if not is_ffprobe_available():
        raise RuntimeError("ffprobe is not installed or available on PATH.")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            logger.error("ffprobe returned code %d: %s", res.returncode, res.stderr)
            raise ValueError("The uploaded file is not a supported or valid media file.")

        data = json.loads(res.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Duration
        duration_sec = 0.0
        if "duration" in fmt:
            try:
                duration_sec = float(fmt["duration"])
            except (ValueError, TypeError):
                duration_sec = 0.0

        file_size = int(fmt.get("size", file_path.stat().st_size if file_path.exists() else 0))
        bitrate = int(fmt.get("bit_rate", 0))

        # Stream extraction
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        width = 0
        height = 0
        video_codec = None
        fps = 0.0

        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            video_codec = video_stream.get("codec_name")
            # Calculate FPS
            r_frame_rate = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = map(int, r_frame_rate.split("/"))
                fps = round(num / den, 2) if den != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0

            if not duration_sec and "duration" in video_stream:
                try:
                    duration_sec = float(video_stream["duration"])
                except (ValueError, TypeError):
                    pass

        audio_codec = None
        if audio_stream:
            audio_codec = audio_stream.get("codec_name")
            if not duration_sec and "duration" in audio_stream:
                try:
                    duration_sec = float(audio_stream["duration"])
                except (ValueError, TypeError):
                    pass

        resolution = f"{width}x{height}" if width and height else "Unknown"

        if video_stream is None and audio_stream is None:
            raise ValueError("The uploaded file does not contain an audio or video stream.")

        return {
            "duration": round(duration_sec, 2),
            "duration_formatted": format_duration(duration_sec),
            "size": file_size,
            "size_formatted": format_bytes(file_size),
            "width": width,
            "height": height,
            "resolution": resolution,
            "video_codec": video_codec or "None",
            "audio_codec": audio_codec or "None",
            "bitrate": bitrate,
            "fps": fps,
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None,
        }

    except Exception as exc:
        logger.exception("Error probing file %s: %s", file_path, exc)
        if isinstance(exc, ValueError):
            raise
        raise ValueError("The uploaded file could not be read as valid media.") from exc

