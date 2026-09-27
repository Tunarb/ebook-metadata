from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from ..models import Evidence

CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_NS = "http://www.idpf.org/2007/opf"
NS = {"dc": DC_NS, "opf": OPF_NS}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(data: bytes) -> ET.Element:
    # Some otherwise valid EPUBs contain NUL padding after the XML root element.
    # NUL is not legal XML, so ElementTree reports these files as malformed even
    # though the actual metadata document is intact. Remove only trailing NUL
    # bytes; malformed XML inside the document must still fail normally.
    data = data.rstrip(b"\x00")
    return ET.fromstring(data)


def collect(candidate) -> tuple[list[Evidence], dict | None]:
    path = Path(candidate.ebook_path)
    evidence: list[Evidence] = []
    cover: dict | None = None
    try:
        with zipfile.ZipFile(path) as zf:
            container = _parse_xml(zf.read("META-INF/container.xml"))
            rootfiles = container.findall(
                f"{{{CONTAINER_NS}}}rootfiles/{{{CONTAINER_NS}}}rootfile"
            )
            if not rootfiles:
                raise ValueError("No OPF rootfile in META-INF/container.xml")
            opf_path = rootfiles[0].attrib["full-path"]
            opf = _parse_xml(zf.read(opf_path))
            opf_dir = posixpath.dirname(opf_path)

            metadata = next((x for x in opf if _local(x.tag) == "metadata"), None)
            if metadata is not None:
                # EPUB 3 uses metadata refinement to distinguish the main title,
                # subtitle and collection/series information. Treating every
                # dc:title as a book title creates false conflicts such as
                # "Twisted Games" vs "Rhys og Bridgets historie" vs "Twisted 2".
                refinements: dict[str, list[tuple[str, str | None]]] = {}
                for child in metadata:
                    if _local(child.tag) != "meta":
                        continue
                    refines = child.attrib.get("refines")
                    prop = child.attrib.get("property")
                    if not refines or not prop:
                        continue
                    refines = refines.lstrip("#")
                    refinements.setdefault(refines, []).append(
                        (prop.casefold(), (child.text or "").strip() or None)
                    )

                belongs_to_collection: list[str] = []
                collection_index: str | None = None

                for child in metadata:
                    key = _local(child.tag)
                    value = (child.text or "").strip()
                    if not value:
                        continue

                    if key == "title":
                        title_type = None
                        child_id = child.attrib.get("id")
                        if child_id:
                            title_type = next(
                                (
                                    value
                                    for prop, value in refinements.get(child_id, [])
                                    if prop == "title-type"
                                ),
                                None,
                            )
                        title_type = title_type.casefold() if title_type else None

                        if title_type in (None, "main"):
                            evidence.append(
                                Evidence("title", value, "epub", str(path), 0.90)
                            )
                        elif title_type == "subtitle":
                            evidence.append(
                                Evidence("subtitle", value, "epub", str(path), 0.90)
                            )
                        # collection titles are represented below by
                        # belongs-to-collection + group-position.

                    elif key == "creator":
                        role = None
                        child_id = child.attrib.get("id")
                        if child_id:
                            role = next(
                                (
                                    value
                                    for prop, value in refinements.get(child_id, [])
                                    if prop == "role"
                                ),
                                None,
                            )
                        if role is None or role.casefold() in {"aut", "author"}:
                            evidence.append(
                                Evidence("author", value, "epub", str(path), 0.90)
                            )

                    elif key == "publisher":
                        evidence.append(
                            Evidence("publisher", value, "epub", str(path), 0.90)
                        )
                    elif key == "language":
                        evidence.append(
                            Evidence("language", value, "epub", str(path), 0.90)
                        )
                    elif key == "date":
                        evidence.append(
                            Evidence("published", value, "epub", str(path), 0.90)
                        )
                    elif key == "description":
                        evidence.append(
                            Evidence("description", value, "epub", str(path), 0.90)
                        )
                    elif key == "subject":
                        evidence.append(
                            Evidence("subject", value, "epub", str(path), 0.90)
                        )
                    elif key == "identifier":
                        scheme = child.attrib.get("scheme") or child.attrib.get(
                            "{http://www.idpf.org/2007/opf}scheme"
                        )
                        value_lower = value.lower().strip()
                        identifier_body = re.sub(
                            r"^(?:urn:)?isbn:",
                            "",
                            value_lower,
                        ).replace("-", "").replace(" ", "")
                        if (
                            scheme
                            and scheme.lower() == "isbn"
                        ) or identifier_body.startswith(("978", "979")):
                            evidence.append(
                                Evidence(
                                    "isbn",
                                    value,
                                    "epub",
                                    str(path),
                                    0.95,
                                    {"scheme": scheme},
                                )
                            )
                    elif key == "source":
                        # dc:source is provenance, not the book's ISBN.
                        continue
                    elif key == "meta":
                        prop = child.attrib.get("property", "").casefold()
                        if prop == "belongs-to-collection":
                            belongs_to_collection.append(value)

                if belongs_to_collection:
                    evidence.append(
                        Evidence(
                            "series",
                            belongs_to_collection[0],
                            "epub",
                            str(path),
                            0.90,
                        )
                    )

                    collection_id = next(
                        (
                            child.attrib.get("id")
                            for child in metadata
                            if _local(child.tag) == "meta"
                            and child.attrib.get("property", "").casefold()
                            == "belongs-to-collection"
                            and (child.text or "").strip() == belongs_to_collection[0]
                        ),
                        None,
                    )
                    if collection_id:
                        collection_index = next(
                            (
                                value
                                for prop, value in refinements.get(collection_id, [])
                                if prop == "group-position"
                            ),
                            None,
                        )
                        if collection_index:
                            evidence.append(
                                Evidence(
                                    "series_index",
                                    collection_index,
                                    "epub",
                                    str(path),
                                    0.90,
                                )
                            )

            manifest = next((x for x in opf if _local(x.tag) == "manifest"), None)
            cover_id = None
            if metadata is not None:
                for child in metadata:
                    if (
                        _local(child.tag) == "meta"
                        and child.attrib.get("name", "").lower() == "cover"
                    ):
                        cover_id = child.attrib.get("content")
            if cover_id and manifest is not None:
                for item in manifest:
                    if (
                        _local(item.tag) == "item"
                        and item.attrib.get("id") == cover_id
                    ):
                        href = item.attrib.get("href")
                        if href:
                            cover_path = posixpath.normpath(
                                posixpath.join(opf_dir, href)
                            )
                            cover = {
                                "path": cover_path,
                                "media_type": item.attrib.get("media-type"),
                                "source": "epub",
                            }
                            break

            # EPUB3 books can mark the cover image with properties="cover-image".
            if cover is None and manifest is not None:
                for item in manifest:
                    if (
                        _local(item.tag) == "item"
                        and "cover-image" in item.attrib.get("properties", "").split()
                    ):
                        href = item.attrib.get("href")
                        if href:
                            cover_path = posixpath.normpath(
                                posixpath.join(opf_dir, href)
                            )
                            cover = {
                                "path": cover_path,
                                "media_type": item.attrib.get("media-type"),
                                "source": "epub",
                            }
                            break
    except Exception as exc:
        candidate.errors.append(
            f"EPUB metadata: {type(exc).__name__}: {exc}"
        )

    return evidence, cover
