"""FFmpeg command executor with live progress tracking and cancellation."""

import asyncio
import logging
import os
import subprocess
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class FFmpegRunner:
    """Runs FFmpeg processes and updates live progress via a callback."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._aborted = False

    def abort(self) -> None:
        """Terminate the running FFmpeg process."""
        self._aborted = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                # If still alive after 2 seconds, kill it
                threading.Timer(2.0, self._force_kill).start()
            except Exception as e:
                logger.error("Error terminating FFmpeg process: %s", e)

    def _force_kill(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass

    async def run(
        self,
        cmd: List[str],
        total_duration_sec: float,
        on_progress: Optional[Callable[[float, str, str], None]] = None,
    ) -> bool:
        """Run FFmpeg command asynchronously.
        
        Args:
            cmd: Command list to execute.
            total_duration_sec: Expected duration of output media in seconds.
            on_progress: Callback(percent, speed, eta_str).
            
        Returns:
            True if process exited with 0, False otherwise.
        """
        # Run synchronous subprocess in a worker thread to prevent blocking asyncio loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._run_sync, cmd, total_duration_sec, on_progress
        )

    def _run_sync(
        self,
        cmd: List[str],
        total_duration_sec: float,
        on_progress: Optional[Callable[[float, str, str], None]],
    ) -> bool:
        logger.info("Executing FFmpeg: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # abort() can run after the runner is registered but before Popen
            # has assigned the process. Honor that early cancellation here.
            if self._aborted and self._process.poll() is None:
                self._process.terminate()

            # Drain stderr concurrently to prevent buffer deadlocks
            stderr_lines: List[str] = []

            def _drain_stderr():
                if self._process and self._process.stderr:
                    try:
                        for err in self._process.stderr:
                            stderr_lines.append(err)
                    except Exception:
                        pass

            stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
            stderr_thread.start()

            last_pct = 0.0
            last_speed = ""
            start_wall_time = time.time()

            if self._process.stdout:
                for line in self._process.stdout:
                    if self._aborted:
                        break

                    line = line.strip()
                    if line.startswith("out_time_us="):
                        try:
                            us = int(line.split("=", 1)[1])
                            current_secs = us / 1_000_000.0
                            if total_duration_sec > 0:
                                pct = min(round((current_secs / total_duration_sec) * 100, 1), 99.9)
                                last_pct = pct
                        except (ValueError, ZeroDivisionError):
                            pass
                    elif line.startswith("speed="):
                        last_speed = line.split("=", 1)[1].strip()
                        # Calculate ETA
                        eta_str = ""
                        if total_duration_sec > 0 and last_pct > 0:
                            try:
                                elapsed_wall = time.time() - start_wall_time
                                total_estimated_wall = (elapsed_wall / last_pct) * 100.0
                                remaining_wall = max(0, total_estimated_wall - elapsed_wall)
                                rem_m, rem_s = divmod(int(remaining_wall), 60)
                                eta_str = f"{rem_m:02d}:{rem_s:02d}"
                            except Exception:
                                eta_str = ""

                        if on_progress:
                            on_progress(last_pct, last_speed, eta_str)

            self._process.wait()
            ret_code = self._process.returncode

            if self._aborted:
                logger.info("FFmpeg process was aborted by user.")
                return False

            if ret_code != 0:
                err_msg = "".join(stderr_lines[-20:])
                logger.error("FFmpeg failed (code %d): %s", ret_code, err_msg)
                return False

            if on_progress:
                on_progress(100.0, "Done", "00:00")

            return True

        except Exception as exc:
            logger.exception("Exception running FFmpeg: %s", exc)
            return False
        finally:
            self._process = None
