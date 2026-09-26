"""Strategy registry for media operations."""

from typing import Dict, Optional
from backend.app.services.strategies.base import MediaStrategy
from backend.app.services.strategies.compress import VideoCompressStrategy
from backend.app.services.strategies.audio import AudioExtractStrategy
from backend.app.services.strategies.gif import VideoToGifStrategy

_STRATEGY_MAP: Dict[str, MediaStrategy] = {
    "compress": VideoCompressStrategy(),
    "audio": AudioExtractStrategy(),
    "gif": VideoToGifStrategy(),
}


def get_strategy(strategy_name: str) -> Optional[MediaStrategy]:
    """Retrieve strategy instance by name."""
    return _STRATEGY_MAP.get(strategy_name.lower())


def register_strategy(strategy: MediaStrategy) -> None:
    """Register a new media processing strategy dynamically."""
    _STRATEGY_MAP[strategy.name.lower()] = strategy


def list_available_strategies() -> Dict[str, str]:
    """List all registered strategy names and labels."""
    return {name: strat.display_name for name, strat in _STRATEGY_MAP.items()}
