"""Thread-safe Job state store."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading


@dataclass
class Job:
    """Represents a media processing task."""

    id: str
    original_name: str
    operation: str
    input_path: Path
    options: Dict[str, Any]
    source_meta: Dict[str, Any]

    status: str = "queued"  # "queued", "processing", "completed", "failed", "cancelled"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    queue_position: int = 0

    output_path: Optional[Path] = None
    output_filename: Optional[str] = None
    output_size: int = 0
    error_message: Optional[str] = None

    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job state to dictionary for client response."""
        input_size = self.source_meta.get("size", 0)
        reduction_pct = 0.0
        if self.status == "completed" and input_size > 0 and self.output_size > 0:
            reduction_pct = round(((input_size - self.output_size) / input_size) * 100, 1)

        return {
            "id": self.id,
            "original_name": self.original_name,
            "operation": self.operation,
            "status": self.status,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "queue_position": self.queue_position,
            "output_filename": self.output_filename,
            "output_size": self.output_size,
            "input_size": input_size,
            "reduction_pct": reduction_pct,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "duration": self.source_meta.get("duration", 0),
            "resolution": self.source_meta.get("resolution", "Unknown"),
        }


class JobStore:
    """Thread-safe in-memory storage for jobs."""

    def __init__(self, max_retained: int = 500):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_retained = max_retained

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            self._prune_old()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def remove(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.pop(job_id, None)

    def list_all(self) -> List[Job]:
        with self._lock:
            return list(self._jobs.values())

    def update_queue_positions(self, queued_ids: List[str]) -> None:
        with self._lock:
            for idx, jid in enumerate(queued_ids, start=1):
                if jid in self._jobs:
                    self._jobs[jid].queue_position = idx

    def _prune_old(self) -> None:
        if len(self._jobs) <= self._max_retained:
            return
        # Keep active/queued jobs, discard oldest completed/failed
        finished = [
            j for j in self._jobs.values()
            if j.status in ("completed", "failed", "cancelled")
        ]
        finished.sort(key=lambda x: x.created_at)
        for j in finished:
            if len(self._jobs) <= self._max_retained:
                break
            self._jobs.pop(j.id, None)


# Global job store singleton
job_store = JobStore()
