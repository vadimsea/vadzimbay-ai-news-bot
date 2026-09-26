from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
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
        for item in self.load_published():
            if _normalize_url(item.get("url", "")) != normalized:
                continue
            status = item.get("status", "published")
            if status in {"published", "rejected"}:
                return True
        return False

    def recently_offered_urls(self, hours: int) -> set[str]:
        """URLs already shown to the moderator within `hours`, so runs do not repeat each other."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        urls: set[str] = set()
        for item in self.load_published():
            if item.get("status") != "offered":
                continue
            moment = _entry_time(item)
            if moment and moment >= cutoff:
                urls.add(_normalize_url(item.get("url", "")))
        return urls

    def count_news_on(self, day: date, tz: tzinfo) -> int:
        """News (not promo) offered, published or rejected on the given local day."""
        count = 0
        for item in self.load_published():
            if item.get("status", "published") not in {"offered", "published", "rejected"}:
                continue
            moment = _entry_time(item)
            if moment and moment.astimezone(tz).date() == day:
                count += 1
        return count

    def mark_as_published(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="published")

    def mark_as_offered(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="offered")

    def mark_as_rejected(self, url: str, metadata: dict[str, Any] | None = None) -> None:
        self._mark(url, metadata, status="rejected")

    def promo_keys_posted_for_day(self, day: str) -> set[str]:
        keys: set[str] = set()
        for item in self.load_published():
            if item.get("status") != "promo":
                continue
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            if metadata.get("day") == day and metadata.get("promo_key"):
                keys.add(str(metadata["promo_key"]))
        return keys

    def mark_promo_posted(
        self,
        promo_key: str,
        day: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._mark(
            f"promo://{promo_key}/{day}",
            {"promo_key": promo_key, "day": day, **(metadata or {})},
            status="promo",
        )

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


def _entry_time(item: dict[str, Any]) -> datetime | None:
    moments: list[datetime] = []
    for key in ("published_at", "updated_at"):
        try:
            moment = datetime.fromisoformat(str(item.get(key) or ""))
        except ValueError:
            continue
        moments.append(moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc))
    return max(moments) if moments else None


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")
