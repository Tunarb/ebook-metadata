from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .discovery import discover
from .sources import epub, folder, images, nfo


def scan(source: Path) -> dict:
    candidates = discover(source)
    for candidate in candidates:
        candidate.evidence.extend(folder.collect(candidate))
        candidate.evidence.extend(nfo.collect(candidate))
        epub_evidence, embedded_cover = epub.collect(candidate)
        candidate.evidence.extend(epub_evidence)
        candidate.embedded_cover = embedded_cover
        candidate.external_images = images.collect(candidate)
    return {
        "schema_version": 1,
        "source": str(source),
        "candidate_count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ebook metadata inventory")
    parser.add_argument("--source", default=os.environ.get("RELEASES_PATH", "/data/releases"))
    parser.add_argument("--output", default=os.environ.get("OUTPUT_PATH", "/data/output/inventory.json"))
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")

    report = scan(source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovered {report['candidate_count']} EPUB candidate(s)")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
