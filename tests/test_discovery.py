from ebook_metadata.discovery import discover


def test_standalone_does_not_claim_source_root_files(tmp_path):
    ebook = tmp_path / "Book.epub"
    ebook.write_bytes(b"")
    (tmp_path / "Other.epub").write_bytes(b"")
    (tmp_path / "unrelated.nfo").write_text("x", encoding="utf-8")
    (tmp_path / "unrelated.jpg").write_bytes(b"")

    candidates = discover(tmp_path)

    assert len(candidates) == 2
    for candidate in candidates:
        assert candidate.context_type == "standalone"
        assert candidate.context_is_release_folder is False
        assert candidate.files == [candidate.path.name]
