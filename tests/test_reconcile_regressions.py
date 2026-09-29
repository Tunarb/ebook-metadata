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
