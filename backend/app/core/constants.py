"""Application constants and default configurations for Nobaj."""

from pathlib import Path

# Project paths
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = BACKEND_DIR.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"

# Allowed input video extensions
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ".flv", ".wmv", ".m4v", ".ts", ".3gp", ".mpeg", ".mpg"
}

# Allowed input audio extensions (if uploading audio directly)
ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"
}

# Combined allowed extensions
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS

# Common MIME type verification mappings
ALLOWED_MIME_PREFIXES = ("video/", "audio/", "application/octet-stream")

# Video compression presets and codecs
VIDEO_CODECS = {
    "h264": {"codec": "libx264", "label": "H.264 (Universal Compatibility)"},
    "h265": {"codec": "libx265", "label": "H.265 / HEVC (High Efficiency)"},
    "vp9": {"codec": "libvpx-vp9", "label": "VP9 (WebM Standard)"}
}

VIDEO_RESOLUTIONS = {
    "original": {"label": "Original (الأصلية)", "scale": None},
    "1080p": {"label": "1080p Full HD (1920x1080)", "scale": "1920:-2"},
    "720p": {"label": "720p HD (1280x720)", "scale": "1280:-2"},
    "480p": {"label": "480p SD (854x480)", "scale": "854:-2"},
    "360p": {"label": "360p Low (640x360)", "scale": "640:-2"}
}

COMPRESSION_SPEED_PRESETS = {
    "ultrafast": "Ultrafast (أسرع معالجة - حجم أكبر)",
    "superfast": "Superfast (سريع جداً)",
    "veryfast": "Veryfast (سريع)",
    "faster": "Faster (سريع ومتوازن)",
    "medium": "Medium (متوازن - موصى به)",
    "slow": "Slow (ضغط عالي - جودة فائقة)",
    "slower": "Slower (أقصى ضغط - يستغرق وقت أطول)"
}

# Audio extraction formats
AUDIO_FORMATS = {
    "mp3": {"ext": ".mp3", "codec": "libmp3lame", "mime": "audio/mpeg", "label": "MP3 (الأكثر شيوعاً)"},
    "aac": {"ext": ".aac", "codec": "aac", "mime": "audio/aac", "label": "AAC (جودة عالية)"},
    "wav": {"ext": ".wav", "codec": "pcm_s16le", "mime": "audio/wav", "label": "WAV (غير مضغوط / أصلي)"},
    "flac": {"ext": ".flac", "codec": "flac", "mime": "audio/flac", "label": "FLAC (صوت فائق بدون فقدان)"},
    "ogg": {"ext": ".ogg", "codec": "libvorbis", "mime": "audio/ogg", "label": "OGG Vorbis"}
}

AUDIO_BITRATES = ["64k", "128k", "192k", "256k", "320k"]

# GIF settings
GIF_FPS_OPTIONS = [10, 15, 20, 24, 30]
GIF_RESOLUTIONS = {
    "original": {"label": "Original (الأصلية)", "scale": "original"},
    "320": {"label": "320px (Tiny - حجم صغير جداً)", "scale": "320:-1"},
    "480": {"label": "480px (Standard - مقاس قياسي)", "scale": "480:-1"},
    "640": {"label": "640px (Medium - جودة متوسطة)", "scale": "640:-1"},
    "720": {"label": "720px (HD - عالي الوضوح)", "scale": "720:-1"}
}
