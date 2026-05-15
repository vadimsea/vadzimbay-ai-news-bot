from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class PublishedStorage:
    def __init__(self, path: Path):
        self.path = path

    def load_published(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def is_published(self, url: str) -> bool:
        normalized = _normalize_url(url)
        return any(_normalize_url(item.get("url", "")) == normalized for item in self.load_published())

    def mark_as_published(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        items = self.load_published()
        if self.is_published(url):
            return
        items.append(
            {
                "url": url,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
            }
        )
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")
