"""Health check endpoint."""

from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.services.ffmpeg.probe import is_ffmpeg_available, is_ffprobe_available
from backend.app.services.ffmpeg.gpu import detect_gpu_encoder

router = APIRouter()


@router.get("/health")
async def health_check():
    """Returns application health status and dependencies."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "ffmpeg_available": is_ffmpeg_available(),
        "ffprobe_available": is_ffprobe_available(),
        "gpu": detect_gpu_encoder(),
    }
