from ebook_metadata.enrichment.calibre import enrich_with_calibre
from ebook_metadata.models import BookCandidate


class FakeClient:
    container = "calibre-test"

    def lookup(self, **kwargs):
        from ebook_metadata.calibre.client import CalibreMetadata
        return CalibreMetadata(
            title="Vuggen går",
            authors=["Gyrithe Lemche"],
            publisher="Gyldendal",
            published="1933-09-15T00:00:00+00:00",
            languages=["dan"],
            identifiers={"google": "KUSCXwAACAAJ"},
        )


def test_calibre_enrichment_adds_provenance_without_overwriting_existing_data(tmp_path):
    candidate = BookCandidate(
        str(tmp_path / "vuggen.epub"),
        str(tmp_path / "Vuggen"),
        True,
        "Vuggen",
    )
    from ebook_metadata.models import Evidence
    candidate.evidence.append(Evidence("title", "Vuggen går", "nfo", str(tmp_path / "book.nfo"), 0.85))

    from ebook_metadata.metadata.reconcile import reconcile
    preliminary = reconcile(candidate.evidence)
    enrich_with_calibre(candidate, client=FakeClient(), preliminary=preliminary)

    assert any(
        e.field == "author"
        and e.value == "Gyrithe Lemche"
        and e.source == "calibre"
        for e in candidate.evidence
    )
    assert any(
        e.field == "publisher"
        and e.value == "Gyldendal"
        and e.source == "calibre"
        for e in candidate.evidence
    )
    assert all(e.details.get("lookup_mode") == "title" for e in candidate.evidence if e.source == "calibre")
