from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class TextFileCache:
    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, url: str) -> str | None:
        try:
            value = json.loads(self._path(url).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if time.time() - float(value.get("cached_at", 0)) > self.ttl_seconds:
            return None
        payload = value.get("payload")
        return payload if isinstance(payload, str) else None

    def put(self, url: str, payload: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self._path(url)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"cached_at": time.time(), "payload": payload}), encoding="utf-8"
        )
        temporary.replace(destination)

