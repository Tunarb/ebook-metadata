from __future__ import annotations

import re
from pathlib import Path
from ..models import Evidence

KEYS = {
    "title": "title",
    "publisher": "publisher",
    "language": "language",
    "release date": "published",
    "released": "published",
    "source": "source_url",
}


def collect(candidate) -> list[Evidence]:
    results: list[Evidence] = []
    for path in Path(candidate.context_dir).glob("*.nfo"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = re.match(r"^\.\.(.+?)\.{2,}\s*(.*?)\s*$", line)
            if not match:
                continue
            raw_key, value = match.groups()
            key = raw_key.strip().lower()
            value = value.strip()
            field = KEYS.get(key)
            if field and value:
                results.append(Evidence(field, value, "nfo", str(path), 0.85))
    return results
