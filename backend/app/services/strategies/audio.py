"""Audio Extraction Strategy."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.core.constants import AUDIO_FORMATS
from backend.app.services.strategies.base import MediaStrategy

logger = logging.getLogger(__name__)


class AudioExtractStrategy(MediaStrategy):
    """Strategy for extracting and converting audio from video files."""

    @property
    def name(self) -> str:
        return "audio"

    @property
    def display_name(self) -> str:
        return "Audio Extraction (استخراج الصوت)"

    def get_output_extension(self, options: Dict[str, Any]) -> str:
        fmt = options.get("format", "mp3").lower()
        if fmt in AUDIO_FORMATS:
            return AUDIO_FORMATS[fmt]["ext"]
        return ".mp3"

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

        audio_format = options.get("format", "mp3").lower()
        bitrate = options.get("bitrate", "192k")
        channels = options.get("channels", "original")  # "original", "stereo", "mono"

        cmd = ["ffmpeg", "-y"]

        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])

        cmd.extend(["-i", str(input_path)])

        if end_time > start_time:
            cmd.extend(["-t", str(end_time - start_time)])

        # Strip video entirely
        cmd.extend(["-vn"])

        # Codec configuration
        if audio_format == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])
        elif audio_format == "aac":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate])
        elif audio_format == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif audio_format == "flac":
            cmd.extend(["-c:a", "flac"])
        elif audio_format == "ogg":
            cmd.extend(["-c:a", "libvorbis", "-q:a", "5"])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate])

        # Audio channels
        if channels == "mono":
            cmd.extend(["-ac", "1"])
        elif channels == "stereo":
            cmd.extend(["-ac", "2"])

        cmd.extend(["-progress", "pipe:1", "-nostats"])
        cmd.append(str(output_path))

        return cmd, max(0.1, effective_duration)
