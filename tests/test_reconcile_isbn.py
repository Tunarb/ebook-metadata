from ebook_metadata.metadata.reconcile import reconcile
from ebook_metadata.models import Evidence


def ev(field, value, source, confidence):
    return Evidence(
        field=field,
        value=value,
        source=source,
        source_path=f"{source}://test",
        confidence=confidence,
        details={},
    )


def base():
    return [
        ev("title", "Testbog", "epub", 0.90),
        ev("author", "Test Forfatter", "epub", 0.90),
        ev("language", "da", "epub", 0.90),
    ]


def test_isbn_format_variants_are_equivalent():
    evidence = base() + [
        ev("isbn", "urn:isbn:9788740000000", "epub", 0.95),
        ev("isbn", "9788740000000", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.isbn == "9788740000000"
    assert "isbn conflict" not in " ".join(result.reasons).lower()
    assert result.status == "AUTO"


def test_isbn_hyphenation_is_equivalent():
    evidence = base() + [
        ev("isbn", "978-87-400-0000-0", "epub", 0.95),
        ev("isbn", "9788740000000", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.isbn == "9788740000000"
    assert "isbn conflict" not in " ".join(result.reasons).lower()
    assert result.status == "AUTO"


def test_same_isbn_from_epub_and_calibre_is_not_a_conflict():
    evidence = base() + [
        ev("isbn", "9788740000000", "epub", 0.95),
        ev("isbn", "urn:isbn:9788740000000", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.isbn == "9788740000000"
    assert result.status == "AUTO"
    assert not any("isbn" in reason.lower() and "conflict" in reason.lower()
                   for reason in result.reasons)


def test_different_isbn_values_stay_review():
    evidence = base() + [
        ev("isbn", "9788740000000", "epub", 0.95),
        ev("isbn", "9788740000001", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.status == "REVIEW"
    assert any("isbn" in reason.lower() and "conflict" in reason.lower()
               for reason in result.reasons)


def test_calibre_can_supply_isbn_when_epub_has_none():
    evidence = base() + [
        ev("isbn", "9788740000000", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.isbn == "9788740000000"
    assert result.status == "AUTO"


def test_strong_epub_isbn_is_not_replaced_by_different_calibre_isbn():
    evidence = base() + [
        ev("isbn", "9788740000000", "epub", 0.95),
        ev("isbn", "9788740000001", "calibre", 0.96),
    ]

    result = reconcile(evidence)

    assert result.isbn == "9788740000000"
    assert result.status == "REVIEW"
