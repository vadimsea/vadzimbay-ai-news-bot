from __future__ import annotations

from html import escape
import re


def format_post_html(text: str) -> str:
    lines = text.strip().splitlines()
    if not lines:
        return text

    first_non_empty = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_non_empty is None:
        return text

    formatted: list[str] = []
    for index, line in enumerate(lines):
        escaped = escape(line, quote=False)
        if index == first_non_empty:
            escaped = f"<b>{escaped}</b>"
        formatted.append(escaped)

    return "\n".join(formatted)


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)
