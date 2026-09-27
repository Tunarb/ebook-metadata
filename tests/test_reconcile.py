from ebook_metadata.metadata.reconcile import reconcile
from ebook_metadata.models import Evidence


def test_strong_epub_metadata_can_be_resolved():
    result = reconcile([
        Evidence("title", "Ali pÃ¥ mÃ¥l", "epub", confidence=0.9),
        Evidence("author", "Gry Kappel Jensen", "epub", confidence=0.9),
        Evidence("isbn", "urn:isbn:9788740697445", "epub", confidence=0.95),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "Ali pÃ¥ mÃ¥l"
    assert result.authors == ["Gry Kappel Jensen"]
    assert result.isbn == "9788740697445"
    assert result.languages == ["da"]


def test_release_publisher_beats_calibre_without_review():
    result = reconcile([
        Evidence("title", "Polli", "epub", confidence=0.9),
        Evidence("author", "Guus Kuijer", "epub", confidence=0.9),
        Evidence("language", "da-DK", "epub", confidence=0.9),
        Evidence("publisher", "Carlsen", "nfo", confidence=0.85),
        Evidence("publisher", "Lindhardt og Ringhof", "epub", confidence=0.9),
        Evidence("publisher", "Some Calibre Imprint", "calibre", confidence=0.95),
    ])
    assert result.status == "AUTO"
    assert result.publisher == "Lindhardt og Ringhof"
    assert not any("conflicting publisher" in x for x in result.reasons)


def test_release_date_beats_calibre_without_review():
    result = reconcile([
        Evidence("title", "Natur og opdragelse", "epub", confidence=0.9),
        Evidence("author", "Alfred Bramsen", "epub", confidence=0.9),
        Evidence("language", "da-DK", "epub", confidence=0.9),
        Evidence("published", "2023-12-13", "epub", confidence=0.9),
        Evidence("published", "2024-01-16T14:30:57", "calibre", confidence=0.95),
    ])
    assert result.status == "AUTO"
    assert result.published == "2023-12-13"


def test_longer_calibre_description_supplements_short_release_description():
    result = reconcile([
        Evidence("title", "Testbog", "epub", confidence=0.9),
        Evidence("author", "Test Forfatter", "epub", confidence=0.9),
        Evidence("language", "da-DK", "epub", confidence=0.9),
        Evidence("description", "Kort beskrivelse.", "epub", confidence=0.9),
        Evidence("description", "En meget lÃ¦ngere katalogbeskrivelse fra Calibre.", "calibre", confidence=0.95),
    ])
    assert result.status == "AUTO"
    assert result.description == "En meget lÃ¦ngere katalogbeskrivelse fra Calibre."


def test_combined_calibre_title_matches_structured_release_metadata():
    result = reconcile([
        Evidence("title", "Twisted Games", "epub", confidence=0.9),
        Evidence("subtitle", "Rhys og Bridgets historie", "epub", confidence=0.9),
        Evidence("series", "Twisted", "epub", confidence=0.9),
        Evidence("series_index", "2", "epub", confidence=0.9),
        Evidence(
            "title",
            "Twisted Games - 2: Rhys og Bridgets historie",
            "calibre",
            confidence=0.95,
        ),
        Evidence("author", "Ana Huang", "epub", confidence=0.9),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "Twisted Games"


def test_same_isbn_title_with_folded_subtitle_is_not_a_conflict():
    result = reconcile([
        Evidence("title", "OPLÃ˜S ANGST", "epub", confidence=0.9),
        Evidence("title", "OPLÃ˜S ANGST: HjÃ¦lp Din Hjerne Til Tryghed", "calibre", confidence=0.88),
        Evidence("author", "Kim Oechsle", "epub", confidence=0.9),
        Evidence("isbn", "9788740981797", "epub", confidence=0.95),
        Evidence("isbn", "9788740981797", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "OPLÃ˜S ANGST"
    assert result.reasons == []


def test_same_isbn_title_with_embedded_series_number_is_not_a_conflict():
    result = reconcile([
        Evidence("title", "VÃ¸lvens vej 4 - Ormehavet", "epub", confidence=0.9),
        Evidence("title", "VÃ¸lvens vej - Ormehavet", "calibre", confidence=0.88),
        Evidence("author", "Anne-Marie VedsÃ¸ Olesen", "epub", confidence=0.9),
        Evidence("isbn", "9788727204482", "epub", confidence=0.95),
        Evidence("isbn", "9788727204482", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "VÃ¸lvens vej - Ormehavet"
    assert result.reasons == []


def test_same_isbn_title_with_folded_hyphen_subtitle_is_not_a_conflict():
    result = reconcile([
        Evidence("title", "Vølvens vej", "epub", confidence=0.9),
        Evidence("title", "Vølvens vej - Snehild", "calibre", confidence=0.88),
        Evidence("author", "Anne-Marie Vedsø Olesen", "epub", confidence=0.9),
        Evidence("isbn", "9788711986004", "epub", confidence=0.95),
        Evidence("isbn", "9788711986004", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "Vølvens vej"
    assert result.reasons == []


def test_same_isbn_title_with_calibre_shorter_than_epub_is_not_a_conflict():
    result = reconcile([
        Evidence("title", "Døde sjæle synger ikke: Krimithriller", "epub", confidence=0.9),
        Evidence("title", "Døde sjæle synger ikke", "calibre", confidence=0.88),
        Evidence("author", "Jussi Adler-Olsen, Line Holm", "epub", confidence=0.9),
        Evidence("isbn", "9788740076905", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "AUTO"
    assert result.title == "Døde sjæle synger ikke: Krimithriller"
    assert result.reasons == []


def test_same_isbn_numeric_title_suffix_still_requires_review():
    result = reconcile([
        Evidence("title", "Bog 1", "epub", confidence=0.9),
        Evidence("title", "Bog", "calibre", confidence=0.88),
        Evidence("author", "Test Forfatter", "epub", confidence=0.9),
        Evidence("isbn", "9788740981797", "epub", confidence=0.95),
        Evidence("isbn", "9788740981797", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_different_titles_with_same_isbn_still_require_review():
    result = reconcile([
        Evidence("title", "Bog A", "epub", confidence=0.9),
        Evidence("title", "Helt anden titel", "calibre", confidence=0.88),
        Evidence("author", "Test Forfatter", "epub", confidence=0.9),
        Evidence("isbn", "9788740981797", "epub", confidence=0.95),
        Evidence("isbn", "9788740981797", "calibre", confidence=0.96),
        Evidence("language", "da-DK", "epub", confidence=0.9),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_malformed_epub_stays_review_without_author():
    result = reconcile([
        Evidence("filename_candidate", "Dick Francis Tilgiv Mig", "folder", confidence=0.35),
    ], ["EPUB metadata: ParseError"])
    assert result.status == "REVIEW"
    assert result.title is None
    assert result.authors == []


def test_ascii_folder_title_matches_danish_diacritics_from_epub():
    result = reconcile([
        Evidence("title", "Vuggen Gar", "folder", confidence=0.70),
        Evidence("title", "Vuggen går", "epub", confidence=0.90),
        Evidence("author", "Gyrithe Lemche", "epub", confidence=0.90),
        Evidence("language", "da", "epub", confidence=0.90),
    ])
    assert result.status == "AUTO"
    assert result.title == "Vuggen går"
    assert result.reasons == []


def test_unrelated_titles_still_require_review_even_with_same_strong_source_types():
    result = reconcile([
        Evidence("title", "Mork", "folder", confidence=0.70),
        Evidence("title", "Mørk", "epub", confidence=0.90),
        Evidence("title", "Helt anden titel", "nfo", confidence=0.85),
        Evidence("author", "Test Forfatter", "epub", confidence=0.90),
        Evidence("language", "da", "epub", confidence=0.90),
    ])
    assert result.status == "REVIEW"
    assert any("conflicting title" in reason for reason in result.reasons)


def test_weak_folder_title_does_not_conflict_with_strong_epub_title():
    result = reconcile([
        Evidence("title", "The Puppet Master", "epub", confidence=0.90),
        Evidence("title", "Sam Holland", "folder", confidence=0.70),
        Evidence("author", "Sam Holland", "epub", confidence=0.90),
        Evidence("author", "The Puppet Master", "folder", confidence=0.75),
        Evidence("language", "en", "epub", confidence=0.90),
    ])
    assert result.status == "AUTO"
    assert result.title == "The Puppet Master"
    assert result.authors == ["Sam Holland"]
    assert result.reasons == []


def test_weak_ascii_folder_title_does_not_conflict_with_strong_diacritic_title():
    result = reconcile([
        Evidence("title", "Grædekonen", "epub", confidence=0.90),
        Evidence("title", "Gradekonen", "folder", confidence=0.70),
        Evidence("author", "Camilla Läckberg", "epub", confidence=0.90),
        Evidence("author", "Camilla Lackberg", "folder", confidence=0.75),
        Evidence("language", "da", "epub", confidence=0.90),
    ])
    assert result.status == "AUTO"
    assert result.title == "Grædekonen"
    assert result.authors == ["Camilla Läckberg"]
    assert result.reasons == []


def test_epub_series_metadata_does_not_become_title_conflict():
    result = reconcile([
        Evidence("title", "Røgslør", "epub", confidence=0.90),
        Evidence("series", "Blod over Øresund", "epub", confidence=0.90),
        Evidence("series_index", "3", "epub", confidence=0.90),
        Evidence("author", "Nis Jakob", "epub", confidence=0.90),
        Evidence("author", "Jeanette Bergenstav", "epub", confidence=0.90),
        Evidence("language", "da", "epub", confidence=0.90),
    ])
    assert result.status == "AUTO"
    assert result.title == "Røgslør"
    assert result.series == "Blod over Øresund"
    assert result.series_index == 3.0
