from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from ..models import Evidence

ISBN_RE = re.compile(r"[^0-9Xx]")
LANGUAGE_MAP = {
    "da": "da",
    "dan": "da",
    "da-dk": "da",
    "danish": "da",
    "en": "en",
    "eng": "en",
    "en-us": "en",
    "sv": "sv",
    "swe": "sv",
    "no": "no",
    "nob": "no",
    "nb": "no",
    "de": "de",
    "deu": "de",
    "de-de": "de",
}

TITLE_SEPARATOR_RE = re.compile(r"\s*(?:[-–—:|]\s*)+")
BOOK_INDEX_RE = re.compile(
    r"\b(?:bog|book|bind|volume|vol\.?)\s*\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)


@dataclass
class ResolvedMetadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    isbn: str | None = None
    series: str | None = None
    series_index: float | None = None
    subtitle: str | None = None
    publisher: str | None = None
    languages: list[str] = field(default_factory=list)
    published: str | None = None
    description: str | None = None
    subjects: list[str] = field(default_factory=list)
    identifiers: dict[str, str] = field(default_factory=dict)
    status: str = "REVIEW"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _values(evidence: list[Evidence], field: str) -> list[Evidence]:
    return [e for e in evidence if e.field == field and e.value not in (None, "")]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _normalize_isbn(value: str) -> str | None:
    raw = ISBN_RE.sub("", value or "")
    raw = raw.upper()
    if len(raw) not in (10, 13):
        return None
    if not (raw[:-1].isdigit() and (raw[-1].isdigit() or raw[-1] == "X")):
        return None
    return raw


def _normalize_language(value: str) -> str | None:
    key = value.strip().casefold()
    return LANGUAGE_MAP.get(key, key if len(key) == 2 else None)


def _normalize_title(value: str) -> str:
    value = str(value).strip().casefold()
    value = value.replace("’", "'")
    value = value.replace("–", "-")
    value = value.replace("—", "-")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*-\s*", " - ", value)
    value = re.sub(r"\s*:\s*", ": ", value)
    return value.strip(" .,:;-|")


def _title_comparison_key(value: str) -> str:
    """Normalize titles for conservative ASCII-style release-name comparison."""
    value = _normalize_title(value)
    if not value:
        return ""
    value = value.replace("æ", "ae").replace("ø", "o").replace("å", "a")
    value = value.replace("Æ", "ae").replace("Ø", "o").replace("Å", "a")
    value = unicodedata.normalize("NFKD", value)
    return "".join(char for char in value if not unicodedata.combining(char))


def _title_parts(value: str) -> list[str]:
    normalized = _normalize_title(value)
    if not normalized:
        return []
    parts = TITLE_SEPARATOR_RE.split(normalized)
    return [part.strip(" .,:;-|") for part in parts if part.strip(" .,:;-|")]


def _strip_book_index(value: str) -> str:
    value = BOOK_INDEX_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip(" .,:;-|")


def _strip_embedded_numeric_index(value: str) -> str:
    """Remove a standalone numeric book/series index from a title.

    This is intentionally narrow: only a standalone number surrounded by
    title separators/whitespace is removed, so ordinary numbers inside words
    or titles such as "1984" are preserved.
    """
    value = re.sub(r"(?<=\s)\d+(?:\.\d+)?(?=\s|[-:|])", " ", value)
    value = re.sub(r"(?<=^)(?:\d+(?:\.\d+)?)(?=\s|[-:|])", " ", value)
    return re.sub(r"\s+", " ", value).strip(" .,:;-|")


def _title_equivalent(
    first: str,
    second: str,
    *,
    subtitles: list[str] | None = None,
    series_indices: list[str] | None = None,
) -> bool:
    """Return True when two titles are compatible representations."""
    left = _normalize_title(first)
    right = _normalize_title(second)

    if not left or not right:
        return False

    if left == right:
        return True

    subtitles = [
        _normalize_title(value)
        for value in (subtitles or [])
        if value and _normalize_title(value)
    ]
    indices = [
        _normalize_title(value)
        for value in (series_indices or [])
        if value and _normalize_title(value)
    ]

    # Embedded numeric series/book numbers can occur in either title form.
    # Check this before prefix/suffix handling because the number may sit in
    # the middle of the title.
    if _strip_embedded_numeric_index(left) == _strip_embedded_numeric_index(right):
        return True

    shorter, longer = sorted((left, right), key=len)

    if not longer.startswith(shorter):
        return False

    remainder = longer[len(shorter):].strip(" .,:;-|")
    if not remainder:
        return True

    remainder = _normalize_title(remainder)
    acceptable_suffixes: list[str] = []

    for subtitle in subtitles:
        acceptable_suffixes.append(subtitle)
        for index in indices:
            acceptable_suffixes.extend(
                [
                    f"{index}: {subtitle}",
                    f"{index} {subtitle}",
                    f"{subtitle} {index}",
                ]
            )

    for index in indices:
        acceptable_suffixes.extend(
            [
                index,
                f"bog {index}",
                f"book {index}",
                f"bind {index}",
            ]
        )

    for suffix in acceptable_suffixes:
        if remainder == _normalize_title(suffix):
            return True

    stripped_remainder = _strip_book_index(remainder)
    for subtitle in subtitles:
        if stripped_remainder == subtitle:
            return True

    return False


def _choose(evidence: list[Evidence], field: str) -> tuple[str | None, list[str]]:
    items = _values(evidence, field)
    if not items:
        return None, []

    all_values = _unique([str(e.value) for e in items])
    max_conf = max((e.confidence or 0.0) for e in items)
    top = [e for e in items if (e.confidence or 0.0) == max_conf]
    top_values = _unique([str(e.value) for e in top])
    chosen = top_values[0] if top_values else all_values[0]

    if len(all_values) > 1:
        return chosen, [f"conflicting {field} evidence: {all_values}"]

    return chosen, []


STRONG_METADATA_SOURCES = {"epub", "nfo", "calibre"}
WEAK_DERIVED_SOURCES = {"folder", "filename"}


def _metadata_items(
    evidence: list[Evidence], field: str
) -> list[Evidence]:
    """Return strong metadata evidence when available.

    Folder/filename parsing is deliberately weak evidence. Once a real
    metadata source has supplied a value, a conflicting release-name heuristic
    must not turn an otherwise unambiguous book into REVIEW.
    """
    items = _values(evidence, field)
    strong = [
        item for item in items
        if item.source.casefold() in STRONG_METADATA_SOURCES
    ]
    return strong or items


def _choose_title(
    evidence: list[Evidence],
) -> tuple[str | None, list[str]]:
    items = _metadata_items(evidence, "title")
    if not items:
        return None, []

    all_values = _unique([str(e.value) for e in items])

    if len(all_values) <= 1:
        return all_values[0], []

    subtitles = _unique([str(e.value) for e in _values(evidence, "subtitle")])
    series_indices = _unique(
        [str(e.value) for e in _values(evidence, "series_index")]
    )

    # First determine whether the title values are merely different
    # representations of the same structured metadata.
    title_items = {str(e.value): e for e in items}
    isbn_values = {
        _normalize_isbn(str(e.value))
        for e in _values(evidence, "isbn")
        if _normalize_isbn(str(e.value))
    }

    def pair_equivalent(first: str, second: str) -> bool:
        if _title_equivalent(
            first,
            second,
            subtitles=subtitles,
            series_indices=series_indices,
        ):
            return True

        # Release folders are often generated from ASCII-safe names, so Danish
        # letters can be stripped ("Når" -> "Nar", "går" -> "Gar"). Only
        # accept that equivalence when the weak folder/filename evidence agrees
        # with a stronger metadata source. Do not make accent-insensitive title
        # matching a general-purpose conflict bypass.
        first_item = title_items[first]
        second_item = title_items[second]
        sources = {first_item.source.casefold(), second_item.source.casefold()}
        if sources & {"folder", "filename"} and sources & {"epub", "nfo", "calibre"}:
            if _title_comparison_key(first) == _title_comparison_key(second):
                return True

        # Calibre sometimes folds a release-local subtitle into the title.
        # Only allow this form when the ISBN agrees and the pair is explicitly
        # release-local EPUB metadata versus Calibre metadata. This prevents a
        # generic same-ISBN title disagreement from becoming AUTO.
        if len(isbn_values) == 1:
            first_item = title_items[first]
            second_item = title_items[second]
            sources = {first_item.source.casefold(), second_item.source.casefold()}
            if sources == {"epub", "calibre"}:
                epub_title = (
                    first if first_item.source.casefold() == "epub" else second
                )
                calibre_title = (
                    first if first_item.source.casefold() == "calibre" else second
                )
                epub_norm = _normalize_title(epub_title)
                calibre_norm = _normalize_title(calibre_title)
                shorter, longer = sorted((epub_norm, calibre_norm), key=len)
                if longer.startswith(shorter):
                    remainder = longer[len(shorter):]
                    if remainder.startswith((" - ", ": ", " | ")):
                        suffix = remainder[3:].strip()
                        if suffix and re.search(r"[A-Za-zÆØÅæøåÀ-ÖØ-öø-ÿ]", suffix):
                            return True

        return False

    equivalent = all(
        pair_equivalent(first, second)
        for index, first in enumerate(all_values)
        for second in all_values[index + 1:]
    )

    if equivalent:
        # Prefer the shortest compatible title. This preserves a structured
        # release title such as "Twisted Games" instead of choosing a
        # catalogue title that has folded subtitle/series information into it.
        # When Calibre merely folds a subtitle into the title, keep the EPUB
        # title as the canonical value. This preserves the stronger release
        # metadata while still accepting both title representations.
        epub_titles = [
            value
            for value in all_values
            if title_items[value].source.casefold() == "epub"
        ]
        calibre_titles = [
            value
            for value in all_values
            if title_items[value].source.casefold() == "calibre"
        ]
        for epub_title in epub_titles:
            epub_norm = _normalize_title(epub_title)
            for calibre_title in calibre_titles:
                calibre_norm = _normalize_title(calibre_title)
                shorter, longer = sorted((epub_norm, calibre_norm), key=len)
                if longer.startswith(shorter):
                    remainder = longer[len(shorter):]
                    if remainder.startswith((" - ", ": ", " | ")):
                        suffix = remainder[3:].strip()
                        if suffix and re.search(r"[A-Za-zÆØÅæøåÀ-ÖØ-öø-ÿ]", suffix):
                            return epub_title, []

        # When a weak ASCII-normalized folder/filename title matches stronger
        # metadata, keep the stronger source's spelling (including Danish
        # diacritics) as the canonical title.
        for value in all_values:
            if title_items[value].source.casefold() in {"epub", "nfo", "calibre"}:
                weak_match = any(
                    other != value
                    and title_items[other].source.casefold() in {"folder", "filename"}
                    and _title_comparison_key(other) == _title_comparison_key(value)
                    for other in all_values
                )
                if weak_match:
                    return value, []

        # Otherwise keep the shortest compatible representation.
        chosen = min(
            all_values,
            key=lambda value: (
                len(_normalize_title(value)),
                _normalize_title(value),
            ),
        )
        return chosen, []

    max_conf = max((e.confidence or 0.0) for e in items)
    top = [e for e in items if (e.confidence or 0.0) == max_conf]
    top_values = _unique([str(e.value) for e in top])
    chosen = top_values[0] if top_values else all_values[0]

    return chosen, [f"conflicting title evidence: {all_values}"]


SOURCE_PRIORITY = {
    "epub": 40,
    "nfo": 35,
    "folder": 30,
    "filename": 25,
    "calibre": 20,
}


def _preferred_value(
    evidence: list[Evidence], field: str, *, longest: bool = False
) -> str | None:
    """Choose a value using source priority, then confidence."""
    items = _values(evidence, field)
    if not items:
        return None

    max_source = max(SOURCE_PRIORITY.get(e.source.casefold(), 10) for e in items)
    source_items = [
        e
        for e in items
        if SOURCE_PRIORITY.get(e.source.casefold(), 10) == max_source
    ]

    if longest:
        return max(
            (str(e.value).strip() for e in items),
            key=len,
            default=None,
        )

    max_conf = max((e.confidence or 0.0) for e in source_items)
    top = [e for e in source_items if (e.confidence or 0.0) == max_conf]
    values = _unique([str(e.value) for e in top])

    return values[0] if values else None


def _enriched_field(
    evidence: list[Evidence], field: str, *, longest: bool = False
) -> str | None:
    """Pick a useful value without treating normal enrichment differences as conflicts."""
    return _preferred_value(evidence, field, longest=longest)


def reconcile(
    evidence: list[Evidence],
    errors: list[str] | None = None,
) -> ResolvedMetadata:
    result = ResolvedMetadata()
    reasons: list[str] = []

    result.title, title_reasons = _choose_title(evidence)
    reasons.extend(title_reasons)

    if result.title is None:
        result.title, _ = _choose(evidence, "title_candidate")
        if result.title is None:
            reasons.append("no reliable title evidence")

    author_items = _metadata_items(evidence, "author")
    authors = _unique([str(e.value) for e in author_items])
    result.authors = authors

    if not authors:
        reasons.append("no reliable author evidence")

    isbn_items = _values(evidence, "isbn")
    isbns = _unique(
        [
            x
            for x in (
                _normalize_isbn(str(e.value))
                for e in isbn_items
            )
            if x
        ]
    )

    if len(isbns) == 1:
        result.isbn = isbns[0]
    elif len(isbns) > 1:
        # Conflicting ISBNs must remain REVIEW, but preserve the strongest
        # release-local ISBN as the provisional value. Calibre enrichment is
        # intentionally lower priority than EPUB/NFO/folder evidence, so a
        # catalogue mismatch cannot silently replace a strong EPUB ISBN.
        isbn_candidates = [
            item
            for item in isbn_items
            if _normalize_isbn(str(item.value)) in isbns
        ]
        if isbn_candidates:
            strongest = max(
                isbn_candidates,
                key=lambda item: (
                    SOURCE_PRIORITY.get(item.source.casefold(), 10),
                    item.confidence or 0.0,
                ),
            )
            result.isbn = _normalize_isbn(str(strongest.value))

        reasons.append(f"conflicting ISBN evidence: {isbns}")

    result.series, series_reasons = _choose(evidence, "series")
    reasons.extend(series_reasons)

    result.subtitle, subtitle_reasons = _choose(evidence, "subtitle")
    reasons.extend(subtitle_reasons)

    series_index, series_index_reasons = _choose(evidence, "series_index")
    reasons.extend(series_index_reasons)

    if series_index is not None:
        try:
            result.series_index = float(series_index)
        except ValueError:
            reasons.append(f"invalid series index: {series_index!r}")

    result.publisher = _enriched_field(evidence, "publisher")
    result.published = _enriched_field(evidence, "published")
    result.description = _enriched_field(
        evidence,
        "description",
        longest=True,
    )

    result.subjects = _unique(
        [str(e.value) for e in _values(evidence, "subject")]
    )

    for item in _values(evidence, "identifier"):
        raw = str(item.value)

        if ":" in raw:
            key, value = raw.split(":", 1)
            result.identifiers.setdefault(key.casefold(), value)
        else:
            result.identifiers.setdefault("unknown", raw)

    languages = _unique(
        [
            lang
            for lang in (
                _normalize_language(str(e.value))
                for e in _values(evidence, "language")
            )
            if lang
        ]
    )

    result.languages = languages

    if not languages:
        reasons.append("no normalized language evidence")

    if errors:
        reasons.extend(errors)

    result.reasons = _unique(reasons)
    result.status = (
        "AUTO"
        if not result.reasons and result.title and result.authors
        else "REVIEW"
    )

    return result
