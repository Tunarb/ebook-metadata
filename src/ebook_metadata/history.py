from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def candidate_id(source_root: Path, ebook_path: str) -> str:
    """Return a stable ID for an EPUB based on its source-relative path."""
    path = Path(ebook_path)
    try:
        relative = path.relative_to(source_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    digest = hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest()
    return digest[:20]


def scan_id() -> str:
    """Create a sortable UTC scan identifier."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def append_history(
    history_path: Path,
    *,
    scan_identifier: str,
    scanned_at: str,
    source_root: Path,
    candidate: dict[str, Any],
    resolved: dict[str, Any],
) -> None:
    """Append one immutable candidate snapshot to the JSONL history."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    ebook_path = str(candidate.get("ebook_path", ""))
    record = {
        "history_schema_version": 1,
        "event_type": "scan",
        "scan_id": scan_identifier,
        "scanned_at": scanned_at,
        "candidate_id": candidate_id(source_root, ebook_path),
        "source_relative_path": _relative_path(source_root, ebook_path),
        "ebook_path": ebook_path,
        "status": resolved.get("status"),
        "evidence": candidate.get("evidence", []),
        "errors": candidate.get("errors", []),
        "resolved": resolved,
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _relative_path(source_root: Path, ebook_path: str) -> str:
    try:
        return Path(ebook_path).relative_to(source_root).as_posix()
    except ValueError:
        return Path(ebook_path).as_posix()
