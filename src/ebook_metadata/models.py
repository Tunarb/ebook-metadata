from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Evidence:
    field: str
    value: Any
    source: str
    source_path: str | None = None
    confidence: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImageInfo:
    path: str
    format: str | None = None
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    likely_cover: bool = False
    reason: str | None = None


@dataclass
class BookCandidate:
    ebook_path: str
    context_dir: str
    context_is_release_folder: bool
    folder_name: str
    files: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    external_images: list[ImageInfo] = field(default_factory=list)
    embedded_cover: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [e.to_dict() if isinstance(e, Evidence) else e for e in self.evidence]
        return data

    @property
    def path(self) -> Path:
        return Path(self.ebook_path)
