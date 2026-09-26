"""Video to GIF Conversion Strategy."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.core.constants import GIF_RESOLUTIONS
from backend.app.services.strategies.base import MediaStrategy

logger = logging.getLogger(__name__)


class VideoToGifStrategy(MediaStrategy):
    """Strategy for converting video to high-quality animated GIF."""

    @property
    def name(self) -> str:
        return "gif"

    @property
    def display_name(self) -> str:
        return "Video to GIF (تحويل إلى GIF)"

    def get_output_extension(self, options: Dict[str, Any]) -> str:
        return ".gif"

    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        options: Dict[str, Any],
        source_meta: Dict[str, Any],
    ) -> Tuple[List[str], float]:
        total_duration = float(source_meta.get("duration", 0.0))

        start_time = float(options.get("trim_start", 0.0) or 0.0)
        end_time = float(options.get("trim_end", 0.0) or 0.0)

        effective_duration = total_duration
        if end_time > start_time:
            effective_duration = end_time - start_time
        elif start_time > 0 and total_duration > start_time:
            effective_duration = total_duration - start_time

        fps = int(options.get("fps", 15))
        fps = max(1, min(fps, 30))

        res_key = str(options.get("resolution", "480"))
        scale_val = GIF_RESOLUTIONS.get(res_key, {}).get("scale", "480:-1")
        if scale_val == "original" or not scale_val:
            scale_filter = ""
        else:
            scale_filter = f"scale={scale_val}:flags=lanczos,"

        cmd = ["ffmpeg", "-y"]

        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])

        cmd.extend(["-i", str(input_path)])

        if end_time > start_time:
            cmd.extend(["-t", str(end_time - start_time)])

        # High-fidelity GIF filter chain:
        # 1. Target fps
        # 2. Lanczos scaling
        # 3. Two-stream split: one generates optimal 256-color palette with diff stats,
        #    the second uses that palette with Bayer dithering to eliminate color banding.
        filter_complex = (
            f"fps={fps},"
            f"{scale_filter}"
            f"split[s0][s1];"
            f"[s0]palettegen=stats_mode=diff[p];"
            f"[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
        )

        cmd.extend(["-vf", filter_complex, "-loop", "0"])
        cmd.extend(["-progress", "pipe:1", "-nostats"])
        cmd.append(str(output_path))

        return cmd, max(0.1, effective_duration)
