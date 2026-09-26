"""Security utilities, filename sanitization, and input validation."""

import re
import unicodedata
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings
from backend.app.core.constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_PREFIXES,
    ALLOWED_VIDEO_EXTENSIONS,
)


def sanitize_filename(filename: str) -> str:
    """Clean a user-supplied filename, removing path traversal and unsafe characters.
    
    Args:
        filename: Raw user filename.
        
    Returns:
        Safe alphanumeric/dash/underscore filename preserving extension.
    """
    if not filename:
        return "unnamed_media"

    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)
    # Strip directory components
    filename = Path(filename).name

    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    # Clean characters
    clean_stem = re.sub(r"[^\w\s\.-]", "", stem).strip()
    clean_stem = re.sub(r"[-\s]+", "-", clean_stem)
    if not clean_stem:
        clean_stem = "file"

    return f"{clean_stem[:100]}{ext}"


def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """Verify target_path is strictly inside base_dir to avoid Path Traversal."""
    try:
        target_path.resolve().relative_to(base_dir.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def validate_file_upload(upload_file: UploadFile) -> Tuple[str, str]:
    """Validate incoming uploaded file for extension and content type.
    
    Args:
        upload_file: The FastAPI UploadFile.
        
    Returns:
        Tuple of (clean_filename, extension).
        
    Raises:
        HTTPException if validation fails.
    """
    if not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload."
        )

    clean_name = sanitize_filename(upload_file.filename)
    ext = Path(clean_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Validate content-type if provided
    content_type = upload_file.content_type or ""
    if content_type:
        content_type_lower = content_type.lower()
        if not any(content_type_lower.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME content type: '{content_type}'"
            )

    return clean_name, ext
