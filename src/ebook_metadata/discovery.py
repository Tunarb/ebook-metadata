from __future__ import annotations

from pathlib import Path
from .models import BookCandidate


def discover(source: Path) -> list[BookCandidate]:
    candidates: list[BookCandidate] = []

    for ebook in sorted(source.rglob("*.epub"), key=lambda p: str(p).lower()):
        context = ebook.parent
        is_direct_child = context == source
        files = sorted(p.name for p in context.iterdir() if p.is_file())
        # A direct child of the configured source is a standalone release, not
        # a release folder. Nested EPUBs get their containing directory as the
        # release context, even if that directory only contains the EPUB.
        release_context = not is_direct_child
        candidates.append(
            BookCandidate(
                ebook_path=str(ebook),
                context_dir=str(context),
                context_is_release_folder=release_context,
                folder_name=context.name if release_context else "",
                files=files,
            )
        )
    return candidates
