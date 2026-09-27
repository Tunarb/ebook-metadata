from pathlib import Path
import zipfile

from ebook_metadata.models import BookCandidate
from ebook_metadata.sources.epub import collect


def _write_epub(path: Path, opf: bytes) -> None:
    container = b'''<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)


def _candidate(path: Path) -> BookCandidate:
    return BookCandidate(
        ebook_path=str(path),
        context_dir=str(path.parent),
        context_is_release_folder=False,
        folder_name="",
        files=[path.name],
    )


def test_trailing_nul_padding_after_opf_root_is_recoverable(tmp_path):
    opf = b'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Tilgiv mig</dc:title>
    <dc:creator>Dick Francis</dc:creator>
    <dc:identifier>9788726133387</dc:identifier>
    <dc:language>da</dc:language>
  </metadata>
</package>\x00\x00\x00\x00'''
    path = tmp_path / "book.epub"
    _write_epub(path, opf)

    candidate = _candidate(path)
    evidence, _ = collect(candidate)

    assert not candidate.errors
    assert {(e.field, e.value) for e in evidence} >= {
        ("title", "Tilgiv mig"),
        ("author", "Dick Francis"),
        ("isbn", "9788726133387"),
        ("language", "da"),
    }


def test_dc_source_is_not_treated_as_isbn(tmp_path):
    opf = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Rose og Sigurd</dc:title>
    <dc:creator>Puk Krogsøe</dc:creator>
    <dc:identifier>9788711514535</dc:identifier>
    <dc:source>urn:isbn:9788711513552</dc:source>
    <dc:language>da</dc:language>
  </metadata>
</package>'''.encode()
    path = tmp_path / "book.epub"
    _write_epub(path, opf)

    candidate = _candidate(path)
    evidence, _ = collect(candidate)

    isbns = [e.value for e in evidence if e.field == "isbn"]
    assert isbns == ["9788711514535"]


def test_epub3_title_refinements_separate_title_subtitle_and_series(tmp_path):
    opf = b'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         version="3.0">
  <metadata>
    <dc:title id="t1">Twisted Games</dc:title>
    <meta refines="#t1" property="title-type">main</meta>
    <dc:title id="t2">Rhys og Bridgets historie</dc:title>
    <meta refines="#t2" property="title-type">subtitle</meta>
    <meta property="belongs-to-collection" id="c1">Twisted</meta>
    <meta refines="#c1" property="collection-type">series</meta>
    <meta refines="#c1" property="group-position">2</meta>
    <dc:title id="t3">Twisted 2</dc:title>
    <meta refines="#t3" property="title-type">collection</meta>
    <dc:creator id="creator1">Ana Huang</dc:creator>
    <meta refines="#creator1" property="role">aut</meta>
    <dc:creator id="creator2">Editor Person</dc:creator>
    <meta refines="#creator2" property="role">edt</meta>
    <dc:language>da</dc:language>
  </metadata>
</package>'''
    path = tmp_path / "twisted.epub"
    _write_epub(path, opf)

    candidate = _candidate(path)
    evidence, _ = collect(candidate)
    pairs = {(e.field, e.value) for e in evidence}

    assert ("title", "Twisted Games") in pairs
    assert ("subtitle", "Rhys og Bridgets historie") in pairs
    assert ("series", "Twisted") in pairs
    assert ("series_index", "2") in pairs
    assert ("author", "Ana Huang") in pairs
    assert ("title", "Twisted 2") not in pairs
    assert ("author", "Editor Person") not in pairs


def test_urn_isbn_identifier_is_recognized(tmp_path):
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Røgslør</dc:title>
    <dc:creator>Nis Jakob</dc:creator>
    <dc:identifier>urn:isbn:9789180768443</dc:identifier>
    <dc:language>da</dc:language>
  </metadata>
</package>""".encode("utf-8")
    path = tmp_path / "book.epub"
    _write_epub(path, opf)

    candidate = _candidate(path)
    evidence, _ = collect(candidate)

    assert ("isbn", "urn:isbn:9789180768443") in {
        (e.field, e.value) for e in evidence
    }
