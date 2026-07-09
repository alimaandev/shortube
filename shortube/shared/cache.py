from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shortube.core.exceptions import CacheError

logger = logging.getLogger(__name__)


class DiskCache:
    def __init__(self, cache_dir: Path | str, default_ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        hashed = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self.cache_dir / f"{hashed}.json"

    def get(self, key: str) -> Any | None:
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            expires = datetime.fromisoformat(data["_expires"])
            if datetime.now() > expires:
                path.unlink(missing_ok=True)
                return None
            return data["value"]
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Cache read error for key=%s: %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        path = self._key_path(key)
        expires = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
        data: dict[str, Any] = {"_expires": expires.isoformat(), "value": value}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            raise CacheError(f"Failed to write cache for key={key}: {e}")

    def invalidate(self, key: str) -> None:
        self._key_path(key).unlink(missing_ok=True)

    def clear(self) -> None:
        for p in self.cache_dir.glob("*.json"):
            p.unlink(missing_ok=True)
