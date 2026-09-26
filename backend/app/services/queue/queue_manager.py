"""Asynchronous Queue Manager with concurrency control."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.core.config import settings
from backend.app.services.ffmpeg.runner import FFmpegRunner
from backend.app.services.queue.job_store import Job, job_store
from backend.app.services.strategies import get_strategy
from backend.app.services.analytics import analytics

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages FIFO job queue and bounds concurrent FFmpeg processes."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=settings.MAX_QUEUE_SIZE)
        self._queued_job_ids: List[str] = []
        self._active_runners: Dict[str, FFmpegRunner] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start worker loop tasks."""
        if self._running:
            return
        self._running = True
        num_workers = max(1, settings.MAX_CONCURRENT_JOBS)
        logger.info("Starting QueueManager with %d concurrent workers.", num_workers)
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(i + 1))
            self._workers.append(task)

    async def stop(self) -> None:
        """Cancel and stop workers."""
        self._running = False
        for runner in self._active_runners.values():
            runner.abort()
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, job: Job) -> bool:
        """Add job to the queue."""
        if self._queue.full():
            logger.warning("Job queue is full (max: %d)", settings.MAX_QUEUE_SIZE)
            return False

        job_store.add(job)
        self._queued_job_ids.append(job.id)
        job_store.update_queue_positions(self._queued_job_ids)
        # Record the row before making the job visible to workers so a fast
        # conversion cannot finish before its analytics row exists.
        try:
            analytics.record_operation_started(job.id, job.operation, job.source_meta.get("size", 0))
        except Exception:
            logger.exception("Could not record analytics for job %s", job.id)

        await self._queue.put(job.id)
        logger.info("Enqueued job %s (%s). Current queue size: %d", job.id, job.operation, self._queue.qsize())
        return True

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active or queued job."""
        job = job_store.get(job_id)
        if not job:
            return False

        # If currently running
        if job_id in self._active_runners:
            self._active_runners[job_id].abort()
            job.status = "cancelled"
            job.completed_at = time.time()
            self._record_finished(job, "Cancelled by user.")
            return True

        # If still in queue
        if job_id in self._queued_job_ids:
            self._queued_job_ids.remove(job_id)
            job_store.update_queue_positions(self._queued_job_ids)
            job.status = "cancelled"
            job.completed_at = time.time()
            self._record_finished(job, "Cancelled by user.")
            return True

        return False

    async def _worker_loop(self, worker_id: int) -> None:
        """Background worker that continuously pulls jobs from the queue."""
        logger.info("Worker #%d started.", worker_id)
        while self._running:
            try:
                job_id = await self._queue.get()
                if job_id in self._queued_job_ids:
                    self._queued_job_ids.remove(job_id)
                    job_store.update_queue_positions(self._queued_job_ids)

                job = job_store.get(job_id)
                if not job or job.status == "cancelled":
                    self._queue.task_done()
                    continue

                await self._process_job(job)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Worker #%d error: %s", worker_id, e)
                await asyncio.sleep(1)

    async def _process_job(self, job: Job) -> None:
        """Execute the conversion for a single job."""
        logger.info("Processing job %s (%s)", job.id, job.operation)
        job.status = "processing"
        job.started_at = time.time()
        job.progress = 0.0

        strategy = get_strategy(job.operation)
        if not strategy:
            job.status = "failed"
            job.error_message = f"Unknown strategy operation: '{job.operation}'"
            job.completed_at = time.time()
            self._record_finished(job, job.error_message)
            return

        out_ext = strategy.get_output_extension(job.options)
        clean_stem = Path(job.original_name).stem
        out_filename = f"{clean_stem}_{job.operation}_{job.id[:8]}{out_ext}"
        out_path = settings.OUTPUT_PATH / out_filename

        job.output_path = out_path
        job.output_filename = out_filename

        runner = FFmpegRunner()
        self._active_runners[job.id] = runner

        def on_progress(pct: float, speed: str, eta: str):
            job.progress = pct
            job.speed = speed
            job.eta = eta

        try:
            cmd, exp_duration = strategy.build_command(
                input_path=job.input_path,
                output_path=out_path,
                options=job.options,
                source_meta=job.source_meta
            )

            success = await runner.run(cmd, exp_duration, on_progress)

            if success and job.status != "cancelled" and out_path.exists() and out_path.stat().st_size > 0:
                job.status = "completed"
                job.progress = 100.0
                job.output_size = out_path.stat().st_size
                logger.info("Job %s completed successfully: %s (%d bytes)", job.id, out_filename, job.output_size)
            else:
                if job.status != "cancelled":
                    job.status = "failed"
                    job.error_message = "FFmpeg processing failed or produced an empty file."
                    logger.error("Job %s failed.", job.id)

        except Exception as exc:
            logger.exception("Unexpected error processing job %s: %s", job.id, exc)
            job.status = "failed"
            job.error_message = str(exc)
        finally:
            job.completed_at = time.time()
            self._record_finished(job, job.error_message)
            self._active_runners.pop(job.id, None)

    @staticmethod
    def _record_finished(job: Job, error_message: Optional[str] = None) -> None:
        """Keep analytics failures from changing queue or cancellation behavior."""
        try:
            analytics.record_operation_finished(
                job.id,
                job.status,
                job.output_size,
                error_message,
            )
        except Exception:
            logger.exception("Could not record completion analytics for job %s", job.id)


# Global queue manager singleton
queue_manager = QueueManager()
