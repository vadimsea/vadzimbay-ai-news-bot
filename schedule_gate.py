from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo


STATE_FILE = Path("schedule_state.json")


@dataclass(frozen=True)
class Window:
    name: str
    start: time
    end: time


def main() -> None:
    timezone = ZoneInfo(os.getenv("TIMEZONE", "Europe/Minsk"))
    now = datetime.now(timezone)
    windows = [
        _parse_window("morning", os.getenv("MORNING_WINDOW", "09:00-11:50")),
        _parse_window("evening", os.getenv("EVENING_WINDOW", "17:00-20:30")),
    ]
    state = _load_state()

    should_run = False
    reason = "outside windows"
    for window in windows:
        if not _inside_window(now.time(), window):
            continue
        state_key = f"{now.date().isoformat()}:{window.name}"
        target = _target_minute(now.date().isoformat(), window)
        current_minutes = now.hour * 60 + now.minute
        if state.get(state_key):
            reason = f"{window.name} already claimed"
            continue
        if current_minutes >= target:
            state[state_key] = now.isoformat()
            _save_state(state)
            should_run = True
            reason = f"{window.name} due"
            break
        reason = f"{window.name} target not reached"

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"should_run={'true' if should_run else 'false'}\n")
            output.write(f"reason={reason}\n")
    print(f"schedule_gate: should_run={should_run}; reason={reason}; now={now.isoformat()}")


def _parse_window(name: str, value: str) -> Window:
    start_raw, end_raw = value.split("-", maxsplit=1)
    return Window(name=name, start=_parse_time(start_raw), end=_parse_time(end_raw))


def _parse_time(value: str) -> time:
    hour, minute = value.strip().split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _inside_window(value: time, window: Window) -> bool:
    return window.start <= value <= window.end


def _target_minute(date_key: str, window: Window) -> int:
    start = window.start.hour * 60 + window.start.minute
    end = window.end.hour * 60 + window.end.minute
    digest = hashlib.sha256(f"{date_key}:{window.name}".encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16) % max(1, end - start + 1)
    return start + offset


def _load_state() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, str]) -> None:
    recent = dict(sorted(state.items())[-30:])
    STATE_FILE.write_text(json.dumps(recent, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
