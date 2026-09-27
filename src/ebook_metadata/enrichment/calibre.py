from __future__ import annotations

from typing import Any

from ..calibre.client import CalibreClient, CalibreLookupError
from ..metadata.reconcile import reconcile
from ..models import BookCandidate, Evidence


def enrich_with_calibre(
    candidate: BookCandidate,
    *,
    client: CalibreClient,
    preliminary=None,
) -> None:
    """Add Calibre metadata as provenance-preserving evidence.

    Lookup failures are recorded as enrichment errors and do not turn an
    otherwise valid candidate into REVIEW.
    """
    query = _build_query(candidate, preliminary)
    if not query:
        return

    mode = query["mode"]
    details = {"lookup_mode": mode, "query": {k: v for k, v in query.items() if k != "mode"}}

    try:
        metadata = client.lookup(
            title=query.get("title"),
            authors=query.get("authors"),
            isbn=query.get("isbn"),
        )
    except (CalibreLookupError, ValueError) as exc:
        candidate.enrichment_errors.append(f"Calibre lookup ({mode}): {exc}")
        return

    source_path = f"calibre://{client.container}"
    if metadata.title:
        candidate.evidence.append(
            Evidence("title", metadata.title, "calibre", source_path, 0.88, details)
        )
    for author in metadata.authors:
        candidate.evidence.append(
            Evidence("author", author, "calibre", source_path, 0.88, details)
        )
    if metadata.publisher:
        candidate.evidence.append(
            Evidence("publisher", metadata.publisher, "calibre", source_path, 0.82, details)
        )
    if metadata.published:
        candidate.evidence.append(
            Evidence("published", metadata.published, "calibre", source_path, 0.72, details)
        )
    for language in metadata.languages:
        candidate.evidence.append(
            Evidence("language", language, "calibre", source_path, 0.82, details)
        )
    if metadata.series:
        candidate.evidence.append(
            Evidence("series", metadata.series, "calibre", source_path, 0.86, details)
        )
    if metadata.series_index is not None:
        candidate.evidence.append(
            Evidence("series_index", str(metadata.series_index), "calibre", source_path, 0.86, details)
        )
    if metadata.description:
        candidate.evidence.append(
            Evidence("description", metadata.description, "calibre", source_path, 0.78, details)
        )
    for subject in metadata.subjects:
        candidate.evidence.append(
            Evidence("subject", subject, "calibre", source_path, 0.70, details)
        )
    for key, value in metadata.identifiers.items():
        field = "isbn" if key.casefold() == "isbn" else "identifier"
        candidate.evidence.append(
            Evidence(
                field,
                value if field == "isbn" else f"{key}:{value}",
                "calibre",
                source_path,
                0.96 if field == "isbn" else 0.90,
                details,
            )
        )


def _build_query(candidate: BookCandidate, preliminary) -> dict[str, Any] | None:
    isbn = preliminary.isbn if preliminary else None
    title = preliminary.title if preliminary else None
    authors = list(preliminary.authors) if preliminary else []

    if isbn:
        return {"mode": "isbn", "isbn": isbn}

    if not title:
        title_candidates = [
            str(e.value)
            for e in candidate.evidence
            if e.field == "title_candidate" and e.value not in (None, "")
        ]
        title = title_candidates[0] if title_candidates else None

    if title and authors:
        return {"mode": "title_author", "title": title, "authors": authors}

    if title:
        return {"mode": "title", "title": title}

    return None
