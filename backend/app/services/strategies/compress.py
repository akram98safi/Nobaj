"""Video Compression Strategy."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.core.constants import VIDEO_RESOLUTIONS
from backend.app.services.ffmpeg.gpu import detect_gpu_encoder
from backend.app.services.strategies.base import MediaStrategy

logger = logging.getLogger(__name__)


class VideoCompressStrategy(MediaStrategy):
    """Strategy for video compression and downscaling."""

    @property
    def name(self) -> str:
        return "compress"

    @property
    def display_name(self) -> str:
        return "Video Compression (ضغط الفيديو)"

    def get_output_extension(self, options: Dict[str, Any]) -> str:
        fmt = options.get("format", "mp4").lower()
        if fmt == "webm":
            return ".webm"
        if fmt == "mkv":
            return ".mkv"
        return ".mp4"

    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        options: Dict[str, Any],
        source_meta: Dict[str, Any],
    ) -> Tuple[List[str], float]:
        total_duration = float(source_meta.get("duration", 0.0))

        # Check for trim options
        start_time = float(options.get("trim_start", 0.0) or 0.0)
        end_time = float(options.get("trim_end", 0.0) or 0.0)

        effective_duration = total_duration
        if end_time > start_time:
            effective_duration = end_time - start_time
        elif start_time > 0 and total_duration > start_time:
            effective_duration = total_duration - start_time

        codec_opt = options.get("codec", "h264").lower()
        preset = options.get("preset", "medium")
        res_key = options.get("resolution", "original")
        audio_bitrate = options.get("audio_bitrate", "128k")
        target_mode = options.get("target_mode", "crf")  # "crf" or "size"

        cmd = ["ffmpeg", "-y"]

        # Fast seeking if start_time is set
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])

        cmd.extend(["-i", str(input_path)])

        if end_time > start_time:
            duration_to_take = end_time - start_time
            cmd.extend(["-t", str(duration_to_take)])

        # Video filters (Resolution scaling)
        vf_filters: List[str] = []
        if res_key in VIDEO_RESOLUTIONS and VIDEO_RESOLUTIONS[res_key]["scale"]:
            scale_val = VIDEO_RESOLUTIONS[res_key]["scale"]
            # Lanczos scale with accurate round
            vf_filters.append(f"scale={scale_val}:flags=lanczos")

        # Optional pixel format for max compatibility
        vf_filters.append("format=yuv420p")
        cmd.extend(["-vf", ",".join(vf_filters)])

        # Calculate bitrates or CRF
        if target_mode == "size" and options.get("target_size_mb"):
            try:
                target_mb = float(options["target_size_mb"])
                total_bits = target_mb * 8 * 1024 * 1024
                # Reserve audio bitrate (e.g. 128 kbps)
                audio_kbps = int(audio_bitrate.rstrip("k")) if "k" in audio_bitrate else 128
                audio_bits = audio_kbps * 1000 * effective_duration
                video_bits = max(100000, total_bits - audio_bits)
                target_video_bitrate_kbps = max(50, int((video_bits / effective_duration) / 1000))
                
                cmd.extend(["-b:v", f"{target_video_bitrate_kbps}k", "-maxrate", f"{int(target_video_bitrate_kbps * 1.5)}k", "-bufsize", f"{target_video_bitrate_kbps * 2}k"])
            except Exception as e:
                logger.warning("Failed calculating target bitrate, falling back to CRF: %s", e)
                cmd.extend(["-crf", "28"])
        else:
            # Quality level map to CRF
            # Higher CRF = smaller size, lower quality
            quality = options.get("quality", "medium")
            crf_map = {
                "low": 32,       # Aggressive compression (small size)
                "medium": 26,    # Balanced
                "high": 21,      # High visual fidelity
            }
            crf_val = options.get("crf")
            if crf_val is not None:
                try:
                    crf = int(crf_val)
                except (ValueError, TypeError):
                    crf = crf_map.get(quality, 26)
            else:
                crf = crf_map.get(quality, 26)

            if codec_opt == "h265":
                # For H.265, CRF values produce slightly better compression at same number
                cmd.extend(["-crf", str(crf + 2)])
            elif codec_opt == "vp9":
                cmd.extend(["-crf", str(crf + 4), "-b:v", "0"])
            else:
                cmd.extend(["-crf", str(crf)])

        # Choose encoder
        if codec_opt == "h265":
            cmd.extend(["-c:v", "libx265", "-preset", preset])
        elif codec_opt == "vp9":
            cmd.extend(["-c:v", "libvpx-vp9", "-speed", "2"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", preset])

        # Audio settings
        if source_meta.get("has_audio"):
            cmd.extend(["-c:a", "aac", "-b:a", audio_bitrate])
        else:
            cmd.extend(["-an"])

        # Optimization for web streaming
        if output_path.suffix.lower() == ".mp4":
            cmd.extend(["-movflags", "+faststart"])

        # Machine-readable progress
        cmd.extend(["-progress", "pipe:1", "-nostats"])
        cmd.append(str(output_path))

        return cmd, max(0.1, effective_duration)
