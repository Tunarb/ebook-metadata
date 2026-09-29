from __future__ import annotations

from ebook_metadata.metadata.reconcile import reconcile
from ebook_metadata.models import Evidence


def ev(field: str, value: str, source: str, confidence: float = 0.9) -> Evidence:
    return Evidence(field=field, value=value, source=source, confidence=confidence)


def test_empty_evidence_stays_review():
    result = reconcile([])
    assert result.status == "REVIEW"


def test_epub_metadata_is_auto():
    result = reconcile([
        ev("title", "Dune", "epub"),
        ev("author", "Frank Herbert", "epub"),
        ev("isbn", "9780441172719", "epub", 0.95),
        ev("language", "en", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Dune"
    assert result.authors == ["Frank Herbert"]
    assert result.isbn == "9780441172719"


def test_same_isbn_title_variants_are_auto():
    result = reconcile([
        ev("title", "1Q84 - Bog 1", "epub"),
        ev("title", "1Q84 Bog 1", "calibre", 0.88),
        ev("author", "Haruki Murakami", "epub"),
        ev("author", "Haruki Murakami", "calibre", 0.88),
        ev("isbn", "9788777141044", "epub", 0.95),
        ev("isbn", "9788777141044", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.reasons == []


def test_sisyfosmyten_punctuation_variant_is_auto():
    result = reconcile([
        ev("title", "SisyfosMyten", "epub"),
        ev("title", "Sisyfos-myten", "calibre", 0.88),
        ev("author", "Albert Camus", "epub"),
        ev("author", "Albert Camus", "calibre", 0.88),
        ev("isbn", "9788702262544", "epub", 0.95),
        ev("isbn", "9788702262544", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.reasons == []


def test_same_isbn_title_with_folded_subtitle_is_not_a_conflict():
    result = reconcile([
        ev("title", "OPLØS ANGST", "epub"),
        ev("title", "OPLØS ANGST: Hjælp Din Hjerne Til Tryghed", "calibre", 0.88),
        ev("author", "Kim Oechsle", "epub"),
        ev("isbn", "9788740981797", "epub", 0.95),
        ev("isbn", "9788740981797", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "OPLØS ANGST"
    assert result.reasons == []


def test_same_isbn_title_with_embedded_series_number_is_not_a_conflict():
    result = reconcile([
        ev("title", "Vølvens vej 4 - Ormehavet", "epub"),
        ev("title", "Vølvens vej - Ormehavet", "calibre", 0.88),
        ev("author", "Anne-Marie Vedsø Olesen", "epub"),
        ev("isbn", "9788727204482", "epub", 0.95),
        ev("isbn", "9788727204482", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Vølvens vej - Ormehavet"
    assert result.reasons == []


def test_same_isbn_title_with_folded_hyphen_subtitle_is_not_a_conflict():
    result = reconcile([
        ev("title", "Vølvens vej", "epub"),
        ev("title", "Vølvens vej - Snehild", "calibre", 0.88),
        ev("author", "Anne-Marie Vedsø Olesen", "epub"),
        ev("isbn", "9788711986004", "epub", 0.95),
        ev("isbn", "9788711986004", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Vølvens vej"
    assert result.reasons == []


def test_same_isbn_title_with_series_number_and_catalogue_subtitle_is_auto():
    result = reconcile([
        ev("title", "Throne of Glass #5: Lysets dronning", "epub"),
        ev("title", "Lysets dronning", "calibre", 0.88),
        ev("author", "Sarah J. Maas", "epub"),
        ev("author", "Sarah J. Maas", "calibre", 0.88),
        ev("isbn", "9788758841861", "epub", 0.95),
        ev("isbn", "9788758841861", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"


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


def test_2049_catalogue_generic_roman_descriptor_is_equivalent_even_with_bad_folder_author():
    result = reconcile([
        ev("author", "Vendepunktet", "folder", 0.75),
        ev("title", "Johan Peter Beck", "folder", 0.7),
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


def test_where_literature_variant_is_equivalent_with_same_book_index():
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
