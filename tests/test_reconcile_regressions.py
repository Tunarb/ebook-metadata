from ebook_metadata.metadata.reconcile import reconcile
from ebook_metadata.models import Evidence


def ev(field, value, source, confidence=0.9):
    return Evidence(field, value, source, confidence=confidence)


def test_2049_catalogue_generic_roman_descriptor_is_equivalent_even_with_bad_folder_author():
    result = reconcile([
        ev("author", "Vendepunktet", "folder", 0.75),
        ev("title", "Johan Peter Beck", "folder", 0.70),
        ev("title", "2049 Vendepunktet", "epub"),
        ev("title", "2049 - vendepunktet: roman", "calibre", 0.88),
        ev("author", "Johan Peter Beck", "epub"),
        ev("author", "Johan Peter Beck", "calibre", 0.88),
        ev("isbn", "9788770703031", "epub", 0.95),
        ev("isbn", "9788770703031", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "2049 Vendepunktet"


def test_where_literature_indexed_catalogue_variant_is_equivalent():
    result = reconcile([
        ev("title", "Hvor litteraturen finder sted - bind 3: Moderne tider 1900-2010", "nfo", 0.85),
        ev("title", "Hvor litteraturen finder sted 3", "epub"),
        ev("author", "Anne-Marie Mai", "epub"),
        ev("author", "Anne-Marie Mai", "calibre", 0.88),
        ev("isbn", "9788702114201", "epub", 0.95),
        ev("isbn", "9788702114201", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Hvor litteraturen finder sted 3"


def test_folder_author_guess_does_not_block_catalogue_title_reconciliation():
    result = reconcile([
        ev("author", "Vendepunktet", "folder", 0.75),
        ev("author", "Johan Peter Beck", "epub"),
        ev("author", "Johan Peter Beck", "calibre", 0.88),
        ev("title", "2049 Vendepunktet", "epub"),
        ev("title", "2049 - vendepunktet: roman", "calibre", 0.88),
        ev("isbn", "9788770703031", "epub", 0.95),
        ev("isbn", "9788770703031", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"


def test_punctuation_equivalence_does_not_hide_unrelated_titles():
    result = reconcile([
        ev("title", "SisyfosMyten", "epub"),
        ev("title", "Sisyfos-myte", "calibre", 0.88),
        ev("author", "Albert Camus", "epub"),
        ev("isbn", "9788702262544", "epub", 0.95),
        ev("isbn", "9788702262544", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_catalogue_title_can_omit_series_prefix_when_identity_evidence_agrees():
    for number, subtitle, isbn in [
        (5, "Lysets dronning", "9788758841861"),
        (9, "Håbets tårn", "9788758850238"),
    ]:
        result = reconcile([
            ev("title", f"Throne of Glass #{number}: {subtitle}", "epub"),
            ev("title", subtitle, "calibre", 0.88),
            ev("author", "Sarah J. Maas", "epub"),
            ev("author", "Sarah J. Maas", "calibre", 0.88),
            ev("isbn", isbn, "epub", 0.95),
            ev("isbn", isbn, "calibre", 0.96),
            ev("language", "da", "epub"),
        ])
        assert result.status == "AUTO", (number, result.reasons)
        assert result.title == f"Throne of Glass #{number}: {subtitle}"


def test_2049_catalogue_generic_roman_descriptor_is_equivalent():
    result = reconcile([
        ev("title", "2049 Vendepunktet", "epub"),
        ev("title", "2049 - vendepunktet: roman", "calibre", 0.88),
        ev("author", "Johan Peter Beck", "epub"),
        ev("author", "Johan Peter Beck", "calibre", 0.88),
        ev("isbn", "9788770703031", "epub", 0.95),
        ev("isbn", "9788770703031", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "2049 Vendepunktet"


def test_where_literature_variant_is_equivalent_with_same_identity():
    result = reconcile([
        ev("title", "Hvor litteraturen finder sted - bind 3: Moderne tider 1900-2010", "nfo", 0.85),
        ev("title", "Hvor litteraturen finder sted 3", "epub"),
        ev("author", "Anne-Marie Mai", "epub"),
        ev("author", "Anne-Marie Mai", "calibre", 0.88),
        ev("isbn", "9788702114201", "epub", 0.95),
        ev("isbn", "9788702114201", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Hvor litteraturen finder sted 3"


def test_andeloos_elements_remains_review_even_with_same_identity_evidence():
    result = reconcile([
        ev("title", "Åndeløs", "epub"),
        ev("title", "Åndeløs Elements", "calibre", 0.88),
        ev("author", "Brittainy C. Cherry", "epub"),
        ev("author", "Brittainy C. Cherry", "calibre", 0.88),
        ev("isbn", "9788702199116", "epub", 0.95),
        ev("isbn", "9788702199116", "calibre", 0.96),
        ev("language", "da", "epub"),
        ev("series", "Elements", "epub"),
        ev("series_index", "1", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_same_isbn_and_author_does_not_resolve_unrelated_titles():
    result = reconcile([
        ev("title", "Bog A", "epub"),
        ev("title", "Helt anden titel", "calibre", 0.88),
        ev("author", "Test Forfatter", "epub"),
        ev("author", "Test Forfatter", "calibre", 0.88),
        ev("isbn", "9788740981797", "epub", 0.95),
        ev("isbn", "9788740981797", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "REVIEW"
