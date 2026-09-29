from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .calibre.client import CalibreClient
from .discovery import discover
from .history import append_history, scan_id
from .metadata.reconcile import reconcile
from .models import Evidence
from .sources import epub, folder, images, nfo
from .enrichment.calibre import enrich_with_calibre


def scan(
    source: Path,
    *,
    calibre_enabled: bool = False,
    calibre_container: str | None = None,
    history_path: Path | None = None,
    calibre_workers: int | None = None,
) -> dict:
    candidates = discover(source)
    run_id = scan_id()
    scanned_at = datetime.now(timezone.utc).isoformat()

    calibre_client = (
        CalibreClient(container=calibre_container)
        if calibre_enabled
        else None
    )

    for candidate in candidates:
        candidate.evidence.extend(folder.collect(candidate))
        candidate.evidence.extend(nfo.collect(candidate))
        epub_evidence, embedded_cover = epub.collect(candidate)
        candidate.evidence.extend(epub_evidence)
        candidate.embedded_cover = embedded_cover
        candidate.external_images = images.collect(candidate)

    if calibre_client is not None:
        workers = calibre_workers or _env_int("CALIBRE_WORKERS", 4, minimum=1)
        # Each candidate is independent during enrichment. A small thread pool
        # prevents one slow remote metadata provider from serialising the whole
        # scan while avoiding an uncontrolled burst of requests.
        def enrich(candidate):
            item = candidate.to_dict()
            evidence = [Evidence(**entry) for entry in item["evidence"]]
            preliminary = reconcile(evidence, item.get("errors"))
            enrich_with_calibre(
                candidate,
                client=calibre_client,
                preliminary=preliminary,
            )
            return candidate

        with ThreadPoolExecutor(max_workers=workers) as executor:
            candidates = list(executor.map(enrich, candidates))

    data = []
    for candidate in candidates:
        item = candidate.to_dict()
        evidence = [Evidence(**entry) for entry in item["evidence"]]
        resolved = reconcile(evidence, item.get("errors")).to_dict()
        item["resolved"] = resolved

        data.append(item)

        if history_path is not None:
            append_history(
                history_path,
                scan_identifier=run_id,
                scanned_at=scanned_at,
                source_root=source,
                candidate=item,
                resolved=resolved,
            )

    return {
        "schema_version": 4,
        "scan_id": run_id,
        "scanned_at": scanned_at,
        "source": str(source),
        "candidate_count": len(candidates),
        "calibre_enabled": calibre_enabled,
        "calibre_container": calibre_container if calibre_enabled else None,
        "calibre_workers": calibre_workers if calibre_enabled else None,
        "history_path": str(history_path) if history_path else None,
        "candidates": data,
    }


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ebook metadata inventory")
    parser.add_argument("--source", default=os.environ.get("RELEASES_PATH", "/data/releases"))
    parser.add_argument("--output", default=os.environ.get("OUTPUT_PATH", "/data/output/inventory.json"))
    parser.add_argument(
        "--history",
        default=os.environ.get("HISTORY_PATH", "/data/output/history.jsonl"),
    )
    parser.add_argument(
        "--calibre",
        action="store_true",
        default=os.environ.get("CALIBRE_ENABLED", "").casefold() in {"1", "true", "yes", "on"},
        help="Enrich candidates with metadata from the configured Calibre Docker container.",
    )
    parser.add_argument(
        "--calibre-container",
        default=os.environ.get("CALIBRE_CONTAINER", "calibre"),
    )
    parser.add_argument(
        "--calibre-workers",
        type=int,
        default=None,
        help="Maximum concurrent Calibre metadata lookups (default: CALIBRE_WORKERS or 4).",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")

    history_path = Path(args.history).resolve() if args.history else None

    report = scan(
        source,
        calibre_enabled=args.calibre,
        calibre_container=args.calibre_container if args.calibre else None,
        history_path=history_path,
        calibre_workers=args.calibre_workers,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovered {report['candidate_count']} EPUB candidate(s)")
    print(f"Report: {output}")
    if history_path:
        print(f"History: {history_path}")


if __name__ == "__main__":
    main()
