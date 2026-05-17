from __future__ import annotations

from datetime import datetime, timezone
import json
import os
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
        for item in self.load_published():
            if _normalize_url(item.get("url", "")) != normalized:
                continue
            status = item.get("status", "published")
            if status in {"published", "rejected"}:
                return True
            if status == "offered" and _is_fresh_offer(item):
                return True
        return False

    def mark_as_published(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="published")

    def mark_as_offered(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="offered")

    def mark_as_rejected(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="rejected")

    def _mark(self, url: str, metadata: dict[str, Any] | None, status: str) -> None:
        items = self.load_published()
        now = datetime.now(timezone.utc).isoformat()
        normalized = _normalize_url(url)
        for item in items:
            if _normalize_url(item.get("url", "")) != normalized:
                continue
            item["status"] = status
            item["updated_at"] = now
            if status == "published":
                item["published_at"] = now
            item["metadata"] = {**item.get("metadata", {}), **(metadata or {})}
            self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        items.append(
            {
                "url": url,
                "published_at": now,
                "status": status,
                "metadata": metadata or {},
            }
        )
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_fresh_offer(item: dict[str, Any]) -> bool:
    ttl_minutes = int(os.getenv("OFFERED_TTL_MINUTES", "10"))
    if ttl_minutes <= 0:
        return False
    raw = item.get("updated_at") or item.get("published_at")
    if not raw:
        return False
    try:
        offered_at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if offered_at.tzinfo is None:
        offered_at = offered_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - offered_at).total_seconds()
    return age_seconds < ttl_minutes * 60
