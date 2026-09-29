from __future__ import annotations

import copy
import os
import re
import subprocess
import threading
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


class CalibreLookupError(RuntimeError):
    """Raised when Calibre cannot complete a metadata lookup."""


@dataclass
class CalibreMetadata:
    """Metadata returned by Calibre's fetch-ebook-metadata OPF output."""

    title: str | None = None
    authors: list[str] = field(default_factory=list)
    publisher: str | None = None
    published: str | None = None
    description: str | None = None
    languages: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    series: str | None = None
    series_index: float | None = None
    identifiers: dict[str, str] = field(default_factory=dict)
    raw_opf: str = ""


class CalibreClient:
    """Small, testable wrapper around Calibre's CLI in a Docker container.

    The client is deliberately read-only with respect to the Calibre library.
    It only invokes ``fetch-ebook-metadata`` and optionally asks that command
    to download a cover to a temporary location inside the Calibre container.

    Network metadata lookup is the expensive part of the pipeline.  By
    default we restrict Calibre to the two useful built-in metadata sources
    used by this project and use a shorter timeout than Calibre's default.
    Both settings remain configurable through constructor arguments or
    environment variables.
    """

    DEFAULT_PLUGINS = ("Google", "Open Library")
    DEFAULT_TIMEOUT = 15

    def __init__(
        self,
        container: str | None = None,
        docker_binary: str | None = None,
        timeout: int | None = None,
        allowed_plugins: Sequence[str] | None = None,
    ) -> None:
        self.container = container or os.getenv("CALIBRE_CONTAINER", "calibre")
        self.docker_binary = docker_binary or os.getenv("DOCKER_BINARY", "docker")
        self.timeout = (
            timeout
            if timeout is not None
            else _env_int("CALIBRE_TIMEOUT", self.DEFAULT_TIMEOUT, minimum=1)
        )
        self.allowed_plugins = tuple(
            allowed_plugins
            if allowed_plugins is not None
            else _env_list("CALIBRE_ALLOWED_PLUGINS", self.DEFAULT_PLUGINS)
        )
        self._cache: dict[tuple[object, ...], CalibreMetadata | CalibreLookupError] = {}
        self._cache_lock = threading.Lock()

    def lookup(
        self,
        *,
        title: str | None = None,
        authors: Sequence[str] | None = None,
        isbn: str | None = None,
        identifiers: dict[str, str] | None = None,
    ) -> CalibreMetadata:
        """Look up metadata using Calibre and parse its OPF response.

        At least one of title, authors, ISBN or identifier is required.
        ISBNs are passed through as supplied; Calibre performs its own
        identifier lookup. Identifiers use Calibre's ``--identifier`` syntax.
        Results and failures are cached for the lifetime of this scanner run,
        which prevents duplicate network lookups.
        """
        if not any((title, authors, isbn, identifiers)):
            raise ValueError("At least one metadata lookup value is required")

        cache_key = _lookup_key(title, authors, isbn, identifiers)
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            if isinstance(cached, CalibreLookupError):
                raise CalibreLookupError(str(cached))
            return copy.deepcopy(cached)

        args: list[str] = [
            self.docker_binary,
            "exec",
            self.container,
            "fetch-ebook-metadata",
        ]

        if title:
            args.extend(["--title", title])
        if authors:
            args.extend(["--authors", " & ".join(a for a in authors if a)])
        if isbn:
            args.extend(["--isbn", isbn])
        if identifiers:
            for key, value in identifiers.items():
                if key and value:
                    args.extend(["--identifier", f"{key}:{value}"])

        for plugin in self.allowed_plugins:
            args.extend(["--allowed-plugin", plugin])
        args.extend(["--timeout", str(self.timeout), "--opf"])

        try:
            completed = self._run(args)
            if not completed.stdout.strip():
                detail = completed.stderr.strip() or "Calibre returned no OPF metadata"
                raise CalibreLookupError(detail)

            try:
                result = parse_opf(completed.stdout)
            except (ET.ParseError, ValueError) as exc:
                raise CalibreLookupError(f"Could not parse Calibre OPF: {exc}") from exc
        except CalibreLookupError as exc:
            with self._cache_lock:
                self._cache[cache_key] = exc
            raise

        with self._cache_lock:
            self._cache[cache_key] = copy.deepcopy(result)
        return result

    def download_cover(
        self,
        *,
        destination: str | Path,
        title: str | None = None,
        authors: Sequence[str] | None = None,
        isbn: str | None = None,
        identifiers: dict[str, str] | None = None,
    ) -> Path:
        """Download a Calibre cover to a local destination.

        The cover is first written inside the Calibre container and then
        copied out with ``docker cp``. This method does not touch the Calibre
        library.
        """
        if not any((title, authors, isbn, identifiers)):
            raise ValueError("At least one metadata lookup value is required")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        remote = f"/tmp/ebook-metadata-cover-{uuid.uuid4().hex}.jpg"

        args: list[str] = [
            self.docker_binary,
            "exec",
            self.container,
            "fetch-ebook-metadata",
        ]
        if title:
            args.extend(["--title", title])
        if authors:
            args.extend(["--authors", " & ".join(a for a in authors if a)])
        if isbn:
            args.extend(["--isbn", isbn])
        if identifiers:
            for key, value in identifiers.items():
                if key and value:
                    args.extend(["--identifier", f"{key}:{value}"])
        for plugin in self.allowed_plugins:
            args.extend(["--allowed-plugin", plugin])
        args.extend(["--timeout", str(self.timeout), "--cover", remote])

        try:
            completed = self._run(args)
            if not re.search(r"Cover\s*:\s*\S+", completed.stdout):
                raise CalibreLookupError(
                    completed.stderr.strip() or "Calibre did not return a cover"
                )
            self._run(
                [
                    self.docker_binary,
                    "cp",
                    f"{self.container}:{remote}",
                    str(destination),
                ]
            )
        finally:
            try:
                self._run(
                    [self.docker_binary, "exec", self.container, "rm", "-f", remote]
                )
            except Exception:
                pass

        if not destination.is_file():
            raise CalibreLookupError(f"Calibre cover was not copied to {destination}")
        return destination

    def _run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(args),
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise CalibreLookupError(
                f"Docker executable not found: {self.docker_binary}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CalibreLookupError(
                f"Calibre command timed out after {self.timeout}s"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise CalibreLookupError(
                f"Calibre command failed with exit code {exc.returncode}: {detail}"
            ) from exc


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _env_list(name: str, default: Sequence[str]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return tuple(default)
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values


def _lookup_key(
    title: str | None,
    authors: Sequence[str] | None,
    isbn: str | None,
    identifiers: dict[str, str] | None,
) -> tuple[object, ...]:
    return (
        (title or "").strip().casefold(),
        tuple(a.strip().casefold() for a in (authors or ()) if a.strip()),
        (isbn or "").strip().casefold(),
        tuple(sorted((k.strip().casefold(), v.strip().casefold()) for k, v in (identifiers or {}).items())),
    )


def parse_opf(opf: str) -> CalibreMetadata:
    """Parse the OPF emitted by ``fetch-ebook-metadata --opf``."""
    root = ET.fromstring(opf)
    metadata = next(
        (element for element in root if _local_name(element.tag) == "metadata"),
        None,
    )
    if metadata is None:
        raise ValueError("OPF contains no metadata element")

    result = CalibreMetadata(raw_opf=opf)
    creators: list[str] = []

    for element in metadata:
        name = _local_name(element.tag)
        value = _clean_text(element.text)
        if name == "title" and value and result.title is None:
            result.title = value
        elif name == "creator" and value:
            role = _attribute_by_local_name(element, "role")
            if not role or role == "aut":
                if value.lower() != "unknown":
                    creators.append(value)
        elif name == "publisher" and value and result.publisher is None:
            result.publisher = value
        elif name == "date" and value and result.published is None:
            result.published = value
        elif name == "description" and value and result.description is None:
            result.description = value
        elif name == "language" and value:
            result.languages.append(value)
        elif name == "subject" and value:
            result.subjects.append(value)
        elif name == "identifier" and value:
            scheme = _attribute_by_local_name(element, "scheme")
            if scheme and scheme.lower() not in {"calibre", "uuid"}:
                result.identifiers[scheme.lower()] = value
        elif name == "meta":
            meta_name = element.attrib.get("name")
            content = _clean_text(element.attrib.get("content"))
            if meta_name == "calibre:series" and content:
                result.series = content
            elif meta_name == "calibre:series_index" and content:
                try:
                    result.series_index = float(content)
                except ValueError:
                    pass

    result.authors = _dedupe_preserve_order(creators)
    result.languages = _dedupe_preserve_order(result.languages)
    result.subjects = _dedupe_preserve_order(result.subjects)
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attribute_by_local_name(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local_name(key) == name:
            return value
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
