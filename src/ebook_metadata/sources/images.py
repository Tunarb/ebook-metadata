from __future__ import annotations

from pathlib import Path
from PIL import Image
from ..models import ImageInfo

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def collect(candidate) -> list[ImageInfo]:
    result: list[ImageInfo] = []
    for path in sorted(Path(candidate.context_dir).iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        info = ImageInfo(path=str(path))
        try:
            info.bytes = path.stat().st_size
            with Image.open(path) as im:
                info.format = im.format
                info.width, info.height = im.size
            stem = path.stem.lower()
            name_hint = any(x in stem for x in ("cover", "front", "book", "folder"))
            portrait = bool(info.width and info.height and info.height >= info.width)
            info.likely_cover = name_hint or portrait
            info.reason = "filename hint" if name_hint else ("portrait image" if portrait else "no strong cover hint")
        except Exception as exc:
            info.reason = f"unreadable image: {type(exc).__name__}: {exc}"
        result.append(info)
    return result
