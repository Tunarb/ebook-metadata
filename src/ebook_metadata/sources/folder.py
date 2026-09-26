from __future__ import annotations

import re
from pathlib import Path
from ..models import Evidence

RELEASE_MARKERS = re.compile(
    r"(?:DANISH|DANiSH|ENGLISH|eBook|ePub|WEB[-.]?DL|WEB[-.]?StoryRip|StoryRip|SapphireSea)", re.I
)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def collect(candidate) -> list[Evidence]:
    source_name = Path(candidate.context_dir).name if candidate.context_is_release_folder else Path(candidate.ebook_path).stem
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
            return [
                Evidence("author", author, "folder", candidate.context_dir, 0.75),
                Evidence("title", title, "folder", candidate.context_dir, 0.70),
            ]

    if cleaned:
        return [Evidence("filename_candidate", cleaned.replace(".", " "), "filename", candidate.ebook_path, 0.35)]
    return []
