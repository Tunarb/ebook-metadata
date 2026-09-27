from ebook_metadata.history import append_history, candidate_id


def test_candidate_id_is_stable_for_same_relative_path(tmp_path):
    ebook = tmp_path / "Release.Name" / "Book.epub"
    assert candidate_id(tmp_path, str(ebook)) == candidate_id(tmp_path, str(ebook))


def test_history_appends_immutable_jsonl_record(tmp_path):
    history = tmp_path / "history.jsonl"
    source = tmp_path / "releases"
    ebook = source / "Book" / "book.epub"

    candidate = {
        "ebook_path": str(ebook),
        "evidence": [{"field": "title", "value": "Book", "source": "nfo"}],
        "errors": [],
    }
    resolved = {"title": "Book", "status": "AUTO"}

    append_history(
        history,
        scan_identifier="scan-1",
        scanned_at="2026-09-26T12:00:00+00:00",
        source_root=source,
        candidate=candidate,
        resolved=resolved,
    )
    append_history(
        history,
        scan_identifier="scan-2",
        scanned_at="2026-09-26T13:00:00+00:00",
        source_root=source,
        candidate=candidate,
        resolved={"title": "Book", "status": "REVIEW"},
    )

    lines = history.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"scan_id":"scan-1"' in lines[0]
    assert '"scan_id":"scan-2"' in lines[1]
    assert '"source_relative_path":"Book/book.epub"' in lines[0]
