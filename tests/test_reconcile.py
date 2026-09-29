from ebook_metadata.metadata.reconcile import reconcile
from ebook_metadata.models import Evidence


def ev(field, value, source, confidence=0.9):
    return Evidence(field, value, source, confidence=confidence)


def test_strong_epub_metadata_can_be_resolved():
    result = reconcile([
        ev("title", "Ali på mål", "epub"),
        ev("author", "Gry Kappel Jensen", "epub"),
        ev("isbn", "urn:isbn:9788740697445", "epub", 0.95),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Ali på mål"
    assert result.authors == ["Gry Kappel Jensen"]
    assert result.isbn == "9788740697445"
    assert result.languages == ["da"]


def test_release_publisher_beats_calibre_without_review():
    result = reconcile([
        ev("title", "Polli", "epub"),
        ev("author", "Guus Kuijer", "epub"),
        ev("language", "da-DK", "epub"),
        ev("publisher", "Carlsen", "nfo", 0.85),
        ev("publisher", "Lindhardt og Ringhof", "epub"),
        ev("publisher", "Some Calibre Imprint", "calibre", 0.95),
    ])
    assert result.status == "AUTO"
    assert result.publisher == "Lindhardt og Ringhof"
    assert not any("conflicting publisher" in x for x in result.reasons)


def test_release_date_beats_calibre_without_review():
    result = reconcile([
        ev("title", "Natur og opdragelse", "epub"),
        ev("author", "Alfred Bramsen", "epub"),
        ev("language", "da-DK", "epub"),
        ev("published", "2023-12-13", "epub"),
        ev("published", "2024-01-16T14:30:57", "calibre", 0.95),
    ])
    assert result.status == "AUTO"
    assert result.published == "2023-12-13"


def test_longer_calibre_description_supplements_short_release_description():
    result = reconcile([
        ev("title", "Testbog", "epub"),
        ev("author", "Test Forfatter", "epub"),
        ev("language", "da-DK", "epub"),
        ev("description", "Kort beskrivelse.", "epub"),
        ev("description", "En meget længere katalogbeskrivelse fra Calibre.", "calibre", 0.95),
    ])
    assert result.status == "AUTO"
    assert result.description == "En meget længere katalogbeskrivelse fra Calibre."


def test_combined_calibre_title_matches_structured_release_metadata():
    result = reconcile([
        ev("title", "Twisted Games", "epub"),
        ev("subtitle", "Rhys og Bridgets historie", "epub"),
        ev("series", "Twisted", "epub"),
        ev("series_index", "2", "epub"),
        ev("title", "Twisted Games - 2: Rhys og Bridgets historie", "calibre", 0.95),
        ev("author", "Ana Huang", "epub"),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Twisted Games"


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


def test_same_isbn_title_with_calibre_shorter_than_epub_is_not_a_conflict():
    result = reconcile([
        ev("title", "Døde sjæle synger ikke: Krimithriller", "epub"),
        ev("title", "Døde sjæle synger ikke", "calibre", 0.88),
        ev("author", "Jussi Adler-Olsen, Line Holm", "epub"),
        ev("isbn", "9788740076905", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Døde sjæle synger ikke: Krimithriller"
    assert result.reasons == []


def test_same_isbn_numeric_title_suffix_still_requires_review():
    result = reconcile([
        ev("title", "Bog 1", "epub"),
        ev("title", "Bog", "calibre", 0.88),
        ev("author", "Test Forfatter", "epub"),
        ev("isbn", "9788740981797", "epub", 0.95),
        ev("isbn", "9788740981797", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_different_titles_with_same_isbn_still_require_review():
    result = reconcile([
        ev("title", "Bog A", "epub"),
        ev("title", "Helt anden titel", "calibre", 0.88),
        ev("author", "Test Forfatter", "epub"),
        ev("isbn", "9788740981797", "epub", 0.95),
        ev("isbn", "9788740981797", "calibre", 0.96),
        ev("language", "da-DK", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_malformed_epub_stays_review_without_author():
    result = reconcile([ev("filename_candidate", "Dick Francis Tilgiv Mig", "folder", 0.35)], ["EPUB metadata: ParseError"])
    assert result.status == "REVIEW"
    assert result.title is None
    assert result.authors == []


def test_ascii_folder_title_matches_danish_diacritics_from_epub():
    result = reconcile([
        ev("title", "Vuggen Gar", "folder", 0.70),
        ev("title", "Vuggen går", "epub"),
        ev("author", "Gyrithe Lemche", "epub"),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Vuggen går"
    assert result.reasons == []


def test_unrelated_titles_still_require_review_even_with_same_strong_source_types():
    result = reconcile([
        ev("title", "Mork", "folder", 0.70),
        ev("title", "Mørk", "epub"),
        ev("title", "Helt anden titel", "nfo", 0.85),
        ev("author", "Test Forfatter", "epub"),
        ev("language", "da", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_weak_folder_title_does_not_conflict_with_strong_epub_title():
    result = reconcile([
        ev("title", "The Puppet Master", "epub"),
        ev("title", "Sam Holland", "folder", 0.70),
        ev("author", "Sam Holland", "epub"),
        ev("author", "The Puppet Master", "folder", 0.75),
        ev("language", "en", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "The Puppet Master"
    assert result.authors == ["Sam Holland"]
    assert result.reasons == []


def test_weak_ascii_folder_title_does_not_conflict_with_strong_diacritic_title():
    result = reconcile([
        ev("title", "Grædekonen", "epub"),
        ev("title", "Gradekonen", "folder", 0.70),
        ev("author", "Camilla Läckberg", "epub"),
        ev("author", "Camilla Lackberg", "folder", 0.75),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Grædekonen"
    assert result.authors == ["Camilla Läckberg"]
    assert result.reasons == []


def test_epub_series_metadata_does_not_become_title_conflict():
    result = reconcile([
        ev("title", "Røgslør", "epub"),
        ev("series", "Blod over Øresund", "epub"),
        ev("series_index", "3", "epub"),
        ev("author", "Nis Jakob", "epub"),
        ev("author", "Jeanette Bergenstav", "epub"),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert result.title == "Røgslør"
    assert result.series == "Blod over Øresund"
    assert result.series_index == 3.0


def test_1q84_hyphen_difference_is_equivalent():
    result = reconcile([
        ev("title", "1Q84 - Bog 1", "epub"),
        ev("title", "1Q84 Bog 1", "calibre", 0.88),
        ev("author", "Haruki Murakami", "epub"),
        ev("isbn", "9788771290424", "epub", 0.95),
        ev("isbn", "9788771290424", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert not result.reasons


def test_1q84_all_three_book_variants_are_equivalent():
    for number, isbn in [(1, "9788771290424"), (2, "9788771290592"), (3, "9788771291742")]:
        result = reconcile([
            ev("title", f"1Q84 - Bog {number}", "epub"),
            ev("title", f"1Q84 Bog {number}", "calibre", 0.88),
            ev("author", "Haruki Murakami", "epub"),
            ev("isbn", isbn, "epub", 0.95),
            ev("isbn", isbn, "calibre", 0.96),
            ev("language", "da", "epub"),
        ])
        assert result.status == "AUTO"


def test_sisyfosmyten_punctuation_difference_is_equivalent():
    result = reconcile([
        ev("title", "SisyfosMyten", "nfo", 0.85),
        ev("title", "Sisyfos-myten", "epub"),
        ev("title", "Sisyfos-myten", "calibre", 0.88),
        ev("author", "Albert Camus", "epub"),
        ev("isbn", "9788702262544", "epub", 0.95),
        ev("language", "da", "epub"),
    ])
    assert result.status == "AUTO"
    assert not result.reasons


def test_throne_of_glass_book_numbers_are_compatible_with_catalogue_titles():
    cases = [
        (4, "Skyggernes dronning", "9788758840192"),
        (5, "Lysets dronning", "9788758841861"),
        (9, "Håbets tårn", "9788758850238"),
    ]
    for number, subtitle, isbn in cases:
        result = reconcile([
            ev("title", f"Throne of Glass #{number}: {subtitle}", "nfo", 0.85),
            ev("title", f"Throne of Glass - {subtitle}", "calibre", 0.88),
            ev("author", "Sarah J. Maas", "epub"),
            ev("isbn", isbn, "epub", 0.95),
            ev("isbn", isbn, "calibre", 0.96),
            ev("language", "da", "epub"),
        ])
        assert result.status == "AUTO", (number, result.reasons)
        assert not result.reasons


def test_tyson_wrong_calibre_match_stays_review_even_when_isbn_matches():
    result = reconcile([
        ev("title", "Mit livs kamp", "epub"),
        ev("title", "המטבוליזם של המתילציה ב-DNA של תאים איוקריוטים", "calibre", 0.88),
        ev("author", "Mike Tyson", "epub"),
        ev("isbn", "9788771489736", "epub", 0.95),
        ev("isbn", "9788771489736", "calibre", 0.96),
        ev("language", "da", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_andeloos_elements_is_a_real_title_difference():
    result = reconcile([
        ev("title", "Åndeløs", "epub"),
        ev("title", "Åndeløs Elements", "calibre", 0.88),
        ev("author", "Brittainy C. Cherry", "epub"),
        ev("isbn", "9788702199116", "epub", 0.95),
        ev("isbn", "9788702199116", "calibre", 0.96),
        ev("language", "da", "epub"),
        ev("series", "Elements", "epub"),
        ev("series_index", "1", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_where_literature_is_found_title_variant_remains_review_for_now():
    result = reconcile([
        ev("title", "Hvor litteraturen finder sted - bind 3: Moderne tider 1900-2010", "nfo", 0.85),
        ev("title", "Hvor litteraturen finder sted 3", "epub"),
        ev("author", "Anne-Marie Mai", "epub"),
        ev("isbn", "9788702114201", "epub", 0.95),
        ev("language", "da", "epub"),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_missing_author_remains_review():
    result = reconcile([ev("title", "Solarpunk_epub", "epub"), ev("language", "da", "epub")])
    assert result.status == "REVIEW"
    assert "no reliable author evidence" in result.reasons


def test_numeric_title_is_not_treated_as_book_index():
    result = reconcile([
        ev("title", "The 1984", "epub"),
        ev("title", "The", "calibre", 0.88),
        ev("author", "Test Forfatter", "epub"),
        ev("isbn", "9788740981797", "epub", 0.95),
        ev("isbn", "9788740981797", "calibre", 0.96),
        ev("language", "en", "epub"),
    ])
    assert result.status == "REVIEW"


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
