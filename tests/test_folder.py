from ebook_metadata.models import BookCandidate
from ebook_metadata.sources.folder import collect


def test_pitbull_is_release_group_not_title():
    candidate = BookCandidate(
        "/data/book.epub",
        "/data/Alfred.Bramsen.Natur.Og.Opdragelse.2024.DANiSH.eBook.ePub.WEB-DL-PiTBULL",
        True,
        "Alfred.Bramsen.Natur.Og.Opdragelse.2024.DANiSH.eBook.ePub.WEB-DL-PiTBULL",
    )

    evidence = collect(candidate)
    pairs = [(item.field, item.value) for item in evidence]

    assert ("release_group", "PiTBULL") in pairs
    assert ("language_hint", "da") in pairs
    assert ("release_year", "2024") in pairs
    assert ("filename_candidate", "Alfred Bramsen Natur Og Opdragelse") in pairs
    assert not any("PiTBULL" in value for field, value in pairs if field in {"title", "filename_candidate"})


def test_sapphiresea_is_release_group_for_standalone_filename():
    candidate = BookCandidate(
        "/data/Jakob.Bergenstav.Roegsloer.2026.DANiSH.ePub.WEB-DL-SapphireSea.epub",
        "/data",
        False,
        "",
    )

    evidence = collect(candidate)
    pairs = [(item.field, item.value) for item in evidence]

    assert ("release_group", "SapphireSea") in pairs
    assert ("language_hint", "da") in pairs
    assert ("release_year", "2026") in pairs
    assert ("filename_candidate", "Jakob Bergenstav Roegsloer") in pairs
