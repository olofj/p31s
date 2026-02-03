"""
Printer address caching for remembering last-used printer.

Stores the last successfully connected printer address to avoid
repeated scanning/selection across commands.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Default cache TTL: 24 hours
DEFAULT_TTL_SECONDS = 24 * 60 * 60

# Config directory location
CONFIG_DIR = Path.home() / ".config" / "p31s"
CACHE_FILE = CONFIG_DIR / "last_printer"


@dataclass
class CachedPrinter:
    """Cached printer information."""

    address: str
    name: str
    last_used: float  # Unix timestamp


def load_cached_printer(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[CachedPrinter]:
    """Load the cached printer if it exists and hasn't expired.

    Args:
        ttl_seconds: Maximum age of cache in seconds. Default 24 hours.

    Returns:
        CachedPrinter if valid cache exists, None otherwise.
    """
    if not CACHE_FILE.exists():
        return None

    try:
        data = json.loads(CACHE_FILE.read_text())
        cached = CachedPrinter(
            address=data["address"],
            name=data["name"],
            last_used=data["last_used"],
        )

        # Check TTL
        age = time.time() - cached.last_used
        if age > ttl_seconds:
            return None

        return cached
    except (json.JSONDecodeError, KeyError, TypeError):
        # Invalid cache file - treat as missing
        return None


def save_printer(address: str, name: str) -> None:
    """Save printer to cache.

    Args:
        address: Printer Bluetooth address (MAC or UUID)
        name: Printer display name
    """
    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "address": address,
        "name": name,
        "last_used": time.time(),
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def clear_cache() -> bool:
    """Clear the cached printer.

    Returns:
        True if cache was cleared, False if no cache existed.
    """
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        return True
    return False
