from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..models import ImageInfo

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def collect(candidate) -> list[ImageInfo]:
    directory = Path(candidate.context_dir)
    ebook_stem = candidate.path.stem.lower()
    result: list[ImageInfo] = []

    for path in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        # For standalone EPUBs the source root can contain many unrelated
        # images. Only an image with the same basename, or an explicit cover
        # hint, is considered related.
        if not candidate.context_is_release_folder:
            stem = path.stem.lower()
            if stem != ebook_stem and not any(x in stem for x in ("cover", "front")):
                continue

        info = ImageInfo(path=str(path))
        try:
            info.bytes = path.stat().st_size
            with Image.open(path) as im:
                info.format = im.format
                info.width, info.height = im.size
            stem = path.stem.lower()
            name_hint = any(x in stem for x in ("cover", "front", "book", "folder", "poster"))
            portrait = bool(info.width and info.height and info.height >= info.width)
            info.likely_cover = name_hint or portrait
            info.reason = "filename hint" if name_hint else ("portrait image" if portrait else "no strong cover hint")
        except Exception as exc:
            info.reason = f"unreadable image: {type(exc).__name__}: {exc}"
        result.append(info)

    return result
