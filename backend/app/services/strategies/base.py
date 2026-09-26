"""Base Media Strategy interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple


class MediaStrategy(ABC):
    """Protocol for media conversion and processing operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the strategy (e.g., 'compress', 'audio', 'gif')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human readable display name."""
        pass

    @abstractmethod
    def get_output_extension(self, options: Dict[str, Any]) -> str:
        """Return the target file extension including leading dot."""
        pass

    @abstractmethod
    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        options: Dict[str, Any],
        source_meta: Dict[str, Any],
    ) -> Tuple[List[str], float]:
        """Build the FFmpeg command line arguments and compute expected output duration.
        
        Args:
            input_path: Path to uploaded media.
            output_path: Target destination path.
            options: Strategy-specific parameters from the client.
            source_meta: Metadata probed from input file.
            
        Returns:
            Tuple of (command_list, expected_duration_in_seconds).
        """
        pass
