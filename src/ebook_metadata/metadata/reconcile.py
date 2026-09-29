from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from ..models import Evidence

ISBN_RE = re.compile(r"[^0-9Xx]")
LANGUAGE_MAP = {"da":"da","dan":"da","da-dk":"da","danish":"da","en":"en","eng":"en","en-us":"en","sv":"sv","swe":"sv","no":"no","nob":"no","nb":"no","de":"de","deu":"de","de-de":"de"}
TITLE_SEPARATOR_RE = re.compile(r"\s*(?:[-–—:|]\s*)+")
BOOK_INDEX_RE = re.compile(r"\b(?:bog|book|bind|volume|vol\.?)\s*\d+(?:\.\d+)?\b", re.I)
EXPLICIT_INDEX_RE = re.compile(r"(?:#\s*\d+(?:\.\d+)?|\b(?:bog|book|bind|volume|vol\.?)\s*\d+(?:\.\d+)?\b)", re.I)

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
    def to_dict(self) -> dict[str, Any]: return asdict(self)

def _values(evidence: list[Evidence], field: str) -> list[Evidence]:
    return [e for e in evidence if e.field == field and e.value not in (None, "")]

def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set(); result: list[str] = []
    for value in values:
        key = value.casefold().strip()
        if key and key not in seen: seen.add(key); result.append(value.strip())
    return result

def _normalize_isbn(value: str) -> str | None:
    raw = ISBN_RE.sub("", value or "").upper()
    if len(raw) not in (10, 13) or not (raw[:-1].isdigit() and (raw[-1].isdigit() or raw[-1] == "X")): return None
    return raw

def _normalize_language(value: str) -> str | None:
    key = value.strip().casefold(); return LANGUAGE_MAP.get(key, key if len(key) == 2 else None)

def _normalize_title(value: str) -> str:
    value = str(value).strip().casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value); value = re.sub(r"\s*-\s*", " - ", value); value = re.sub(r"\s*:\s*", ": ", value)
    return value.strip(" .,:;-|")

def _title_comparison_key(value: str) -> str:
    value = _normalize_title(value)
    if not value: return ""
    value = value.replace("æ","ae").replace("ø","o").replace("å","a").replace("Æ","ae").replace("Ø","o").replace("Å","a")
    value = unicodedata.normalize("NFKD", value)
    return "".join(char for char in value if not unicodedata.combining(char))

def _title_punctuation_key(value: str) -> str:
    return re.sub(r"[^\w]+", "", _normalize_title(value), flags=re.UNICODE)

def _strip_book_index(value: str) -> str:
    return re.sub(r"\s+", " ", BOOK_INDEX_RE.sub(" ", value)).strip(" .,:;-|")

def _strip_embedded_numeric_index(value: str) -> str:
    value = EXPLICIT_INDEX_RE.sub(" ", value)
    value = re.sub(r"(?<=\s)\d{1,3}(?:\.\d+)?(?=\s|[-:|])", " ", value)
    value = re.sub(r"(?<=^)\d{1,3}(?:\.\d+)?(?=\s|[-:|])", " ", value)
    return re.sub(r"\s+", " ", value).strip(" .,:;-|")

def _extract_explicit_book_index(value: str) -> tuple[str, str] | None:
    normalized = _normalize_title(value)
    if not normalized: return None
    marker = re.search(r"#\s*(\d{1,3}(?:\.\d+)?)", normalized) or re.search(r"\b(?:bog|book|bind|volume|vol\.?)\s*(\d{1,3}(?:\.\d+)?)\b", normalized, re.I)
    if marker:
        base = normalized[:marker.start()].strip(" .,:;-|"); return (base, marker.group(1)) if base else None
    trailing = re.search(r"(?:^|\s)(\d{1,3}(?:\.\d+)?)$", normalized)
    if trailing:
        base = normalized[:trailing.start()].strip(" .,:;-|"); return (base, trailing.group(1)) if base else None
    return None

def _title_equivalent(first: str, second: str, *, subtitles: list[str] | None = None, series_indices: list[str] | None = None) -> bool:
    left, right = _normalize_title(first), _normalize_title(second)
    if not left or not right: return False
    if left == right or _title_punctuation_key(left) == _title_punctuation_key(right): return True
    subtitles = [_normalize_title(v) for v in (subtitles or []) if v and _normalize_title(v)]
    indices = [_normalize_title(v) for v in (series_indices or []) if v and _normalize_title(v)]
    if _title_punctuation_key(_strip_embedded_numeric_index(left)) == _title_punctuation_key(_strip_embedded_numeric_index(right)): return True
    shorter, longer = sorted((left, right), key=len)
    if not longer.startswith(shorter): return False
    remainder = _normalize_title(longer[len(shorter):].strip(" .,:;-|"))
    acceptable: list[str] = []
    for subtitle in subtitles:
        acceptable.append(subtitle)
        for index in indices: acceptable.extend([f"{index}: {subtitle}", f"{index} {subtitle}", f"{subtitle} {index}"])
    for index in indices: acceptable.extend([index, f"bog {index}", f"book {index}", f"bind {index}"])
    if any(remainder == _normalize_title(s) for s in acceptable): return True
    stripped = _strip_book_index(remainder); return any(stripped == subtitle for subtitle in subtitles)

def _choose(evidence: list[Evidence], field: str) -> tuple[str | None, list[str]]:
    items = _values(evidence, field)
    if not items: return None, []
    all_values = _unique([str(e.value) for e in items]); max_conf = max((e.confidence or 0.0) for e in items)
    top_values = _unique([str(e.value) for e in items if (e.confidence or 0.0) == max_conf]); chosen = top_values[0] if top_values else all_values[0]
    return (chosen, [f"conflicting {field} evidence: {all_values}"]) if len(all_values) > 1 else (chosen, [])

STRONG_METADATA_SOURCES = {"epub", "nfo", "calibre"}
WEAK_DERIVED_SOURCES = {"folder", "filename"}

def _metadata_items(evidence: list[Evidence], field: str) -> list[Evidence]:
    items = _values(evidence, field); strong = [item for item in items if item.source.casefold() in STRONG_METADATA_SOURCES]; return strong or items

def _catalogue_structural_equivalent(first: str, second: str) -> bool:
    a, b = _extract_explicit_book_index(first), _extract_explicit_book_index(second)
    if a and b and a[1] == b[1] and _title_punctuation_key(a[0]) == _title_punctuation_key(b[0]): return True
    na, nb = _normalize_title(first), _normalize_title(second); shorter, longer = sorted((na, nb), key=len)
    sl, ss = _strip_embedded_numeric_index(longer), _strip_embedded_numeric_index(shorter)
    if sl and ss and len(re.findall(r"[\wÆØÅæøå]+", ss, flags=re.UNICODE)) >= 2:
        if _title_punctuation_key(sl).endswith(_title_punctuation_key(ss)) or _title_punctuation_key(ss).endswith(_title_punctuation_key(sl)): return True
    for candidate, other in ((na, nb), (nb, na)):
        for descriptor in ("roman", "novel"):
            if re.search(rf"(?:^|[:|])\s*{descriptor}$", candidate):
                base = re.sub(rf"(?:[:|])\s*{descriptor}$", "", candidate).strip()
                if _title_punctuation_key(base) == _title_punctuation_key(other): return True
    return False

def _choose_title(evidence: list[Evidence]) -> tuple[str | None, list[str]]:
    items = _metadata_items(evidence, "title")
    if not items: return None, []
    all_values = _unique([str(e.value) for e in items])
    if len(all_values) <= 1: return all_values[0], []
    subtitles = _unique([str(e.value) for e in _values(evidence, "subtitle")]); series_indices = _unique([str(e.value) for e in _values(evidence, "series_index")]); title_items = {str(e.value): e for e in items}
    isbn_values = {_normalize_isbn(str(e.value)) for e in _values(evidence, "isbn") if _normalize_isbn(str(e.value))}
    author_values = _unique([str(e.value) for e in _metadata_items(evidence, "author")]); strong_identity = len(isbn_values) == 1 and len(author_values) == 1

    def pair_equivalent(first: str, second: str) -> bool:
        if _title_equivalent(first, second, subtitles=subtitles, series_indices=series_indices): return True
        first_item, second_item = title_items[first], title_items[second]; first_source, second_source = first_item.source.casefold(), second_item.source.casefold(); sources = {first_source, second_source}
        if sources & WEAK_DERIVED_SOURCES and sources & STRONG_METADATA_SOURCES and _title_comparison_key(first) == _title_comparison_key(second): return True
        if strong_identity and sources <= STRONG_METADATA_SOURCES and _catalogue_structural_equivalent(first, second): return True
        if len(isbn_values) == 1 and sources == {"epub", "calibre"}:
            epub = first if first_source == "epub" else second; calibre = first if first_source == "calibre" else second; en, cn = _normalize_title(epub), _normalize_title(calibre); shorter, longer = sorted((en, cn), key=len)
            if longer.startswith(shorter):
                rem = longer[len(shorter):]
                if rem.startswith((" - ", ": ", " | ")) and re.search(r"[A-Za-zÆØÅæøåÀ-ÖØ-öø-ÿ]", rem[3:].strip()): return True
        return False

    equivalent = all(pair_equivalent(first, second) for index, first in enumerate(all_values) for second in all_values[index + 1:])
    if not equivalent:
        max_conf = max((e.confidence or 0.0) for e in items); top = _unique([str(e.value) for e in items if (e.confidence or 0.0) == max_conf]); chosen = top[0] if top else all_values[0]
        return chosen, [f"conflicting title evidence: {all_values}"]

    epub_titles = [v for v in all_values if title_items[v].source.casefold() == "epub"]; calibre_titles = [v for v in all_values if title_items[v].source.casefold() == "calibre"]
    for epub_title in epub_titles:
        for calibre_title in calibre_titles:
            en, cn = _normalize_title(epub_title), _normalize_title(calibre_title); shorter, longer = sorted((en, cn), key=len)
            if longer.startswith(shorter):
                rem = longer[len(shorter):]
                if rem.startswith((" - ", ": ", " | ")) and re.search(r"[A-Za-zÆØÅæøåÀ-ÖØ-öø-ÿ]", rem[3:].strip()): return epub_title, []
    for epub_title in epub_titles:
        for calibre_title in calibre_titles:
            if _catalogue_structural_equivalent(epub_title, calibre_title):
                epub_stripped, calibre_stripped = _strip_embedded_numeric_index(epub_title), _strip_embedded_numeric_index(calibre_title)
                numeric_was_removed = _title_punctuation_key(epub_stripped) != _title_punctuation_key(_normalize_title(epub_title)) or _title_punctuation_key(calibre_stripped) != _title_punctuation_key(_normalize_title(calibre_title))
                if numeric_was_removed and _title_punctuation_key(epub_stripped) == _title_punctuation_key(calibre_stripped):
                    return calibre_title, []
                if _title_punctuation_key(epub_stripped) != _title_punctuation_key(calibre_stripped) or re.search(r"(?:^|[:|])\s*(roman|novel)$", _normalize_title(calibre_title)):
                    return epub_title, []
    if epub_titles: return epub_titles[0], []
    return min(all_values, key=lambda value: (len(_normalize_title(value)), _normalize_title(value))), []

SOURCE_PRIORITY = {"epub":40,"nfo":35,"folder":30,"filename":25,"calibre":20}

def _preferred_value(evidence: list[Evidence], field: str, *, longest: bool = False) -> str | None:
    items = _values(evidence, field)
    if not items: return None
    max_source = max(SOURCE_PRIORITY.get(e.source.casefold(), 10) for e in items); source_items = [e for e in items if SOURCE_PRIORITY.get(e.source.casefold(), 10) == max_source]
    if longest: return max((str(e.value).strip() for e in items), key=len, default=None)
    max_conf = max((e.confidence or 0.0) for e in source_items); values = _unique([str(e.value) for e in source_items if (e.confidence or 0.0) == max_conf]); return values[0] if values else None

def _enriched_field(evidence: list[Evidence], field: str, *, longest: bool = False) -> str | None: return _preferred_value(evidence, field, longest=longest)

def reconcile(evidence: list[Evidence], errors: list[str] | None = None) -> ResolvedMetadata:
    result = ResolvedMetadata(); reasons: list[str] = []
    result.title, title_reasons = _choose_title(evidence); reasons.extend(title_reasons)
    if result.title is None:
        result.title, _ = _choose(evidence, "title_candidate")
        if result.title is None: reasons.append("no reliable title evidence")
    author_items = _metadata_items(evidence, "author"); result.authors = _unique([str(e.value) for e in author_items])
    if not result.authors: reasons.append("no reliable author evidence")
    isbn_items = _values(evidence, "isbn"); isbns = _unique([x for x in (_normalize_isbn(str(e.value)) for e in isbn_items) if x])
    if len(isbns) == 1: result.isbn = isbns[0]
    elif len(isbns) > 1:
        candidates = [item for item in isbn_items if _normalize_isbn(str(item.value)) in isbns]
        if candidates:
            strongest = max(candidates, key=lambda item: (SOURCE_PRIORITY.get(item.source.casefold(), 10), item.confidence or 0.0)); result.isbn = _normalize_isbn(str(strongest.value))
        reasons.append(f"conflicting ISBN evidence: {isbns}")
    result.series, series_reasons = _choose(evidence, "series"); reasons.extend(series_reasons)
    result.subtitle, subtitle_reasons = _choose(evidence, "subtitle"); reasons.extend(subtitle_reasons)
    series_index, series_index_reasons = _choose(evidence, "series_index"); reasons.extend(series_index_reasons)
    if series_index is not None:
        try: result.series_index = float(series_index)
        except ValueError: reasons.append(f"invalid series index: {series_index!r}")
    result.publisher = _enriched_field(evidence, "publisher"); result.published = _enriched_field(evidence, "published"); result.description = _enriched_field(evidence, "description", longest=True); result.subjects = _unique([str(e.value) for e in _values(evidence, "subject")])
    for item in _values(evidence, "identifier"):
        raw = str(item.value)
        if ":" in raw: key, value = raw.split(":", 1); result.identifiers.setdefault(key.casefold(), value)
        else: result.identifiers.setdefault("unknown", raw)
    result.languages = _unique([lang for lang in (_normalize_language(str(e.value)) for e in _values(evidence, "language")) if lang])
    if not result.languages: reasons.append("no normalized language evidence")
    if errors: reasons.extend(errors)
    result.reasons = _unique(reasons); result.status = "AUTO" if not result.reasons and result.title and result.authors else "REVIEW"
    return result
