from __future__ import annotations

import re
from pathlib import Path

from ..models import Evidence

RELEASE_GROUP_RE = re.compile(r"(?:^|[-. _])(?P<group>PiTBULL|SapphireSea)(?:$|[-. _])", re.I)
RELEASE_MARKERS = re.compile(
    r"(?:DANISH|DANiSH|ENGLISH|eBook|ePub|WEB[-.]?DL|WEB[-.]?StoryRip|StoryRip|SapphireSea|PiTBULL)",
    re.I,
)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
LANGUAGE_MARKERS = (
    (re.compile(r"DANiSH", re.I), "da"),
    (re.compile(r"DANISH", re.I), "da"),
    (re.compile(r"ENGLISH", re.I), "en"),
)


def _source_name(candidate) -> tuple[str, str]:
    if candidate.context_is_release_folder:
        return Path(candidate.context_dir).name, "folder"
    return Path(candidate.ebook_path).stem, "filename"


def collect(candidate) -> list[Evidence]:
    source_name, source_type = _source_name(candidate)
    source_path = candidate.context_dir if candidate.context_is_release_folder else candidate.ebook_path
    evidence: list[Evidence] = []

    # Release-group names are useful provenance, but must never become part of
    # the title/author candidate. Capture them before cleaning release markers.
    match = RELEASE_GROUP_RE.search(source_name)
    if match:
        evidence.append(
            Evidence(
                "release_group",
                match.group("group"),
                source_type,
                source_path,
                0.95,
                {"raw": source_name},
            )
        )

    for pattern, language in LANGUAGE_MARKERS:
        if pattern.search(source_name):
            evidence.append(Evidence("language_hint", language, source_type, source_path, 0.70))
            break

    year_match = YEAR.search(source_name)
    if year_match:
        evidence.append(Evidence("release_year", year_match.group(0), source_type, source_path, 0.60))

    cleaned = RELEASE_MARKERS.sub(" ", source_name)
    cleaned = YEAR.sub(" ", cleaned)
    cleaned = re.sub(r"[_]+", " ", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_\t")

    # Release names in this collection commonly use Author-Title. This is
    # deliberately weak evidence; the reconciliation layer will decide whether
    # it agrees with NFO/EPUB/Calibre rather than treating it as truth.
    if candidate.context_is_release_folder and "-" in cleaned:
        author, title = cleaned.split("-", 1)
        author = author.replace(".", " ").strip()
        title = title.replace(".", " ").strip()
        if author and title:
            evidence.append(Evidence("author", author, source_type, source_path, 0.75))
            evidence.append(Evidence("title", title, source_type, source_path, 0.70))
            return evidence

    if cleaned:
        evidence.append(
            Evidence(
                "filename_candidate",
                cleaned.replace(".", " "),
                source_type,
                source_path,
                0.35,
            )
        )
    return evidence
