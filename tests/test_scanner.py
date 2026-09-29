from __future__ import annotations

from pathlib import Path

from ebook_metadata.models import BookCandidate
from ebook_metadata.scanner import scan


def test_scan_uses_configured_calibre_worker_count(monkeypatch, tmp_path: Path):
    candidates = [
        BookCandidate(str(tmp_path / f"book{i}.epub"), str(tmp_path / f"Book{i}"), True, f"Book{i}")
        for i in range(3)
    ]

    monkeypatch.setattr("ebook_metadata.scanner.discover", lambda source: candidates)

    class FakeClient:
        def __init__(self, **kwargs):
            self.container = kwargs.get("container")

    calls = []

    def fake_enrich(candidate, *, client, preliminary):
        calls.append(candidate.path)

    monkeypatch.setattr("ebook_metadata.scanner.CalibreClient", FakeClient)
    monkeypatch.setattr("ebook_metadata.scanner.enrich_with_calibre", fake_enrich)

    report = scan(
        tmp_path,
        calibre_enabled=True,
        calibre_container="calibre-test",
        calibre_workers=2,
        history_path=None,
    )

    assert report["candidate_count"] == 3
    assert report["calibre_enabled"] is True
    assert report["calibre_workers"] == 2
    assert sorted(calls) == sorted(candidate.path for candidate in candidates)
