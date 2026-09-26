"""Automatic periodic cleanup of temporary and expired files."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings
from backend.app.services.queue.job_store import job_store

logger = logging.getLogger(__name__)


class AutoCleaner:
    """Periodically purges old uploads and processed outputs to save disk space."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the cleanup periodic task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "AutoCleaner initialized (TTL: %d mins, interval: %d mins).",
            settings.FILE_TTL_MINUTES,
            settings.CLEANUP_INTERVAL_MINUTES,
        )

    async def stop(self) -> None:
        """Stop cleaner task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(settings.CLEANUP_INTERVAL_MINUTES * 60)
                self.purge_expired_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in AutoCleaner loop: %s", e)

    def purge_expired_files(self) -> int:
        """Scan upload and output directories and delete files older than TTL."""
        ttl_seconds = settings.FILE_TTL_MINUTES * 60
        cutoff_time = time.time() - ttl_seconds
        deleted_count = 0
        # A queued or running job may still need its source file or be writing
        # its output. Keep those paths until the job reaches a terminal state.
        protected_paths = set()
        for job in job_store.list_all():
            if job.status in ("queued", "processing"):
                protected_paths.add(job.input_path.resolve())
                if job.output_path:
                    protected_paths.add(job.output_path.resolve())

        target_dirs = [settings.UPLOAD_PATH, settings.OUTPUT_PATH, settings.TEMP_PATH]

        for folder in target_dirs:
            if not folder.exists():
                continue

            for item in folder.iterdir():
                if item.is_file():
                    try:
                        if item.resolve() in protected_paths:
                            continue
                        mtime = item.stat().st_mtime
                        if mtime < cutoff_time:
                            item.unlink(missing_ok=True)
                            deleted_count += 1
                            logger.info("Purged expired file: %s", item.name)
                    except Exception as e:
                        logger.warning("Could not delete %s: %s", item.name, e)

        if deleted_count > 0:
            logger.info("AutoCleaner purged %d expired files.", deleted_count)
        return deleted_count


cleaner = AutoCleaner()
