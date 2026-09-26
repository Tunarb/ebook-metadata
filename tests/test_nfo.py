from ebook_metadata.sources.nfo import collect
from ebook_metadata.models import BookCandidate


def test_nfo_parser(tmp_path):
    nfo = tmp_path / "book.nfo"
    nfo.write_text("..TiTLE........ Ali på mål\n..PUBLiSHER.... Turbine Forlaget\n..LANGUAGE..... DANISH\n", encoding="utf-8")
    c = BookCandidate("/x/book.epub", str(tmp_path), True, tmp_path.name)
    values = collect(c)
    assert [(x.field, x.value) for x in values] == [
        ("title", "Ali på mål"),
        ("publisher", "Turbine Forlaget"),
        ("language", "DANISH"),
    ]
