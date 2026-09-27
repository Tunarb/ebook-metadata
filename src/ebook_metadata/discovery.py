from __future__ import annotations

from pathlib import Path

from .models import BookCandidate


def discover(source: Path) -> list[BookCandidate]:
    """Discover EPUBs without assigning metadata or cross-linking unrelated files.

    A directory directly under the configured source is treated as a standalone
    EPUB location. Nested EPUBs are associated with their containing release
    folder. This distinction is important because the source root may contain
    many unrelated standalone EPUBs.
    """
    candidates: list[BookCandidate] = []

    for ebook in sorted(source.rglob("*.epub"), key=lambda p: str(p).lower()):
        context = ebook.parent
        is_release_folder = context != source

        if is_release_folder:
            files = sorted(
                p.name for p in context.iterdir() if p.is_file()
            )
            context_type = "release_folder"
            folder_name = context.name
        else:
            # Do not expose every file in the source root as belonging to this
            # book. Only the EPUB itself is directly related at discovery time.
            files = [ebook.name]
            context_type = "standalone"
            folder_name = ""

        candidates.append(
            BookCandidate(
                ebook_path=str(ebook),
                context_dir=str(context),
                context_is_release_folder=is_release_folder,
                folder_name=folder_name,
                files=files,
                context_type=context_type,
            )
        )

    return candidates
