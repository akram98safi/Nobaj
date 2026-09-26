"""Main API endpoints for upload, processing, queue status, and downloads."""

import logging
import math
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.constants import (
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    COMPRESSION_SPEED_PRESETS,
    GIF_FPS_OPTIONS,
    GIF_RESOLUTIONS,
    VIDEO_CODECS,
    VIDEO_RESOLUTIONS,
)
from backend.app.core.security import is_safe_path, validate_file_upload
from backend.app.services.ffmpeg.gpu import detect_gpu_encoder
from backend.app.services.ffmpeg.probe import is_ffmpeg_available, probe_file
from backend.app.services.queue.job_store import Job, job_store
from backend.app.services.queue.queue_manager import queue_manager
from backend.app.services.strategies import get_strategy, list_available_strategies
from backend.app.services.analytics import analytics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Temporary cache mapping file_id to source_meta
_file_meta_cache: Dict[str, Dict[str, Any]] = {}


class ProcessRequest(BaseModel):
    file_id: str
    operation: str = Field(..., description="Operation type: 'compress', 'audio', or 'gif'")
    options: Dict[str, Any] = Field(default_factory=dict)


@router.get("/config")
async def get_system_config():
    """Return available settings and preset options for UI rendering."""
    return {
        "app_name": settings.APP_NAME,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "max_duration_seconds": settings.MAX_DURATION_SECONDS,
        "file_ttl_minutes": settings.FILE_TTL_MINUTES,
        "gpu": detect_gpu_encoder(),
        "ffmpeg_ready": is_ffmpeg_available(),
        "video_resolutions": VIDEO_RESOLUTIONS,
        "video_codecs": VIDEO_CODECS,
        "compression_presets": COMPRESSION_SPEED_PRESETS,
        "audio_formats": AUDIO_FORMATS,
        "audio_bitrates": AUDIO_BITRATES,
        "gif_fps": GIF_FPS_OPTIONS,
        "gif_resolutions": GIF_RESOLUTIONS,
        "strategies": list_available_strategies(),
    }


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Stream incoming media file to disk, validate limits, and extract metadata."""
    clean_filename, ext = validate_file_upload(file)

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}{ext}"
    target_path = settings.UPLOAD_PATH / stored_name

    # Stream file to disk in 4MB chunks
    bytes_written = 0
    max_bytes = settings.max_upload_size_bytes

    try:
        async with aiofiles.open(target_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024 * 4):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    # Clean up partial upload
                    await file.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
                    )
                await out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload streaming failed: %s", exc)
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed saving uploaded file."
        )
    finally:
        await file.close()

    # Probe file with ffprobe. Do not accept the fallback metadata for corrupt files.
    try:
        meta = probe_file(target_path)
    except RuntimeError as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta["file_id"] = file_id
    meta["original_name"] = clean_filename
    meta["stored_name"] = stored_name

    # Duration limit check
    duration = meta.get("duration", 0)
    if not math.isfinite(float(duration)) or duration <= 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine the media duration. Please upload a valid audio or video file.",
        )
    if duration > settings.MAX_DURATION_SECONDS:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Media duration ({meta['duration_formatted']}) exceeds maximum permitted duration of {settings.MAX_DURATION_SECONDS // 60} minutes."
        )

    _file_meta_cache[file_id] = meta
    return meta


@router.post("/process")
async def start_process(req: ProcessRequest):
    """Enqueue a conversion job for an uploaded media file."""
    strategy = get_strategy(req.operation)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown operation '{req.operation}'."
        )

    # Find the input file
    meta = _file_meta_cache.get(req.file_id)
    input_file: Optional[Path] = None

    if meta:
        candidate = settings.UPLOAD_PATH / meta["stored_name"]
        if candidate.exists():
            input_file = candidate

    if not input_file:
        # Search by file_id stem in upload dir
        for f in settings.UPLOAD_PATH.iterdir():
            if f.stem == req.file_id:
                input_file = f
                break

    if not input_file or not input_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found or has expired."
        )

    if not meta:
        try:
            meta = probe_file(input_file)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        meta["file_id"] = req.file_id
        meta["original_name"] = input_file.name

    if not math.isfinite(float(meta.get("duration", 0))) or meta.get("duration", 0) <= 0:
        raise HTTPException(status_code=400, detail="Could not determine the media duration.")

    if req.operation in ("compress", "gif") and not meta.get("has_video"):
        raise HTTPException(status_code=400, detail="This operation requires a video file.")
    if req.operation == "audio" and not meta.get("has_audio"):
        raise HTTPException(status_code=400, detail="This operation requires an audio stream.")

    _validate_process_options(req.operation, req.options, float(meta.get("duration", 0)))

    job_id = uuid.uuid4().hex
    job = Job(
        id=job_id,
        original_name=meta.get("original_name", input_file.name),
        operation=req.operation,
        input_path=input_file,
        options=req.options,
        source_meta=meta,
    )

    enqueued = await queue_manager.enqueue(job)
    if not enqueued:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Processing server queue is currently full. Please try again shortly."
        )

    return {
        "job_id": job_id,
        "status": job.status,
        "queue_position": job.queue_position,
        "operation": req.operation,
    }


def _validate_process_options(operation: str, options: Dict[str, Any], duration: float) -> None:
    """Reject invalid options before they reach an FFmpeg command builder."""
    if operation == "compress":
        if options.get("codec", "h264") not in VIDEO_CODECS:
            raise HTTPException(status_code=400, detail="Unsupported video codec.")
        if options.get("resolution", "original") not in VIDEO_RESOLUTIONS:
            raise HTTPException(status_code=400, detail="Unsupported video resolution.")
        if options.get("quality", "medium") not in {"low", "medium", "high"}:
            raise HTTPException(status_code=400, detail="Unsupported compression quality.")
        if options.get("preset", "medium") not in COMPRESSION_SPEED_PRESETS:
            raise HTTPException(status_code=400, detail="Unsupported compression preset.")
        if options.get("audio_bitrate", "128k") not in AUDIO_BITRATES:
            raise HTTPException(status_code=400, detail="Unsupported audio bitrate.")
        if options.get("target_mode", "crf") not in {"crf", "size"}:
            raise HTTPException(status_code=400, detail="Unsupported compression target mode.")
        if options.get("target_mode") == "size":
            try:
                target_size = float(options.get("target_size_mb", 0))
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="Invalid target file size.") from exc
            if not math.isfinite(target_size) or not 1 <= target_size <= 10000:
                raise HTTPException(status_code=400, detail="Target file size must be between 1 and 10000 MB.")
        if "crf" in options:
            try:
                crf = int(options["crf"])
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="Invalid compression quality value.") from exc
            max_crf = 63 if options.get("codec", "h264") == "vp9" else 51
            if not 0 <= crf <= max_crf:
                raise HTTPException(status_code=400, detail=f"Compression quality must be between 0 and {max_crf}.")
    elif operation == "audio":
        if options.get("format", "mp3") not in AUDIO_FORMATS:
            raise HTTPException(status_code=400, detail="Unsupported audio format.")
        if options.get("bitrate", "192k") not in AUDIO_BITRATES:
            raise HTTPException(status_code=400, detail="Unsupported audio bitrate.")
        if options.get("channels", "original") not in {"original", "stereo", "mono"}:
            raise HTTPException(status_code=400, detail="Unsupported audio channel setting.")
    elif operation == "gif":
        try:
            fps = int(options.get("fps", 15))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid GIF frame rate.") from exc
        if fps not in GIF_FPS_OPTIONS:
            raise HTTPException(status_code=400, detail="Unsupported GIF frame rate.")
        if str(options.get("resolution", "480")) not in GIF_RESOLUTIONS:
            raise HTTPException(status_code=400, detail="Unsupported GIF resolution.")

    for name in ("trim_start", "trim_end"):
        if name not in options:
            continue
        try:
            value = float(options[name])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {name} value.") from exc
        if not math.isfinite(value) or value < 0 or (duration > 0 and value > duration):
            raise HTTPException(status_code=400, detail=f"{name} must be within the media duration.")

    if "trim_start" in options and "trim_end" in options:
        if float(options["trim_end"]) <= float(options["trim_start"]):
            raise HTTPException(status_code=400, detail="Trim end must be after trim start.")


@router.get("/stats/public")
async def get_public_stats():
    """Return safe aggregate metrics for the public landing page."""
    return analytics.public_stats()


@router.get("/stats/admin")
async def get_admin_stats(x_admin_token: str | None = Header(default=None)):
    """Return detailed metrics only when the configured admin token is supplied."""
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin dashboard is not configured.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token.")
    return analytics.admin_stats()


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll job status, progress, ETA, and reduction stats."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    return job.to_dict()


@router.post("/job/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    success = queue_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job could not be cancelled (it may have finished or expired)."
        )
    return {"message": "Job cancelled successfully."}


@router.get("/download/{job_id}")
async def download_output(job_id: str):
    """Download the completed processed media file."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )

    if job.status != "completed" or not job.output_path or not job.output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Output is not ready or has expired (Job status: {job.status})."
        )

    # Check path safety
    if not is_safe_path(settings.OUTPUT_PATH, job.output_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid output file path."
        )

    return FileResponse(
        path=job.output_path,
        filename=job.output_filename or job.output_path.name,
        media_type="application/octet-stream"
    )
