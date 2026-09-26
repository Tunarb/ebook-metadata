from __future__ import annotations

import posixpath
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
    # ElementTree is deliberately used here rather than assuming every release
    # contains perfectly valid XML. Bad files are reported to the candidate.
    return ET.fromstring(data)


def collect(candidate) -> tuple[list[Evidence], dict | None]:
    path = Path(candidate.ebook_path)
    evidence: list[Evidence] = []
    cover: dict | None = None
    try:
        with zipfile.ZipFile(path) as zf:
            container = _parse_xml(zf.read("META-INF/container.xml"))
            rootfiles = container.findall(f"{{{CONTAINER_NS}}}rootfiles/{{{CONTAINER_NS}}}rootfile")
            if not rootfiles:
                raise ValueError("No OPF rootfile in META-INF/container.xml")
            opf_path = rootfiles[0].attrib["full-path"]
            opf = _parse_xml(zf.read(opf_path))
            opf_dir = posixpath.dirname(opf_path)

            metadata = next((x for x in opf if _local(x.tag) == "metadata"), None)
            if metadata is not None:
                for child in metadata:
                    key = _local(child.tag)
                    value = (child.text or "").strip()
                    if not value:
                        continue
                    field = {
                        "title": "title",
                        "creator": "author",
                        "publisher": "publisher",
                        "language": "language",
                        "date": "published",
                        "description": "description",
                        "subject": "subject",
                    }.get(key)
                    if field:
                        evidence.append(Evidence(field, value, "epub", str(path), 0.90))
                    if key == "identifier":
                        scheme = child.attrib.get("scheme") or child.attrib.get("{http://www.idpf.org/2007/opf}scheme")
                        value_lower = value.lower()
                        if scheme and scheme.lower() == "isbn" or value_lower.replace("-", "").startswith("978") or value_lower.replace("-", "").startswith("979"):
                            evidence.append(Evidence("isbn", value, "epub", str(path), 0.95, {"scheme": scheme}))

            manifest = next((x for x in opf if _local(x.tag) == "manifest"), None)
            cover_id = None
            if metadata is not None:
                for child in metadata:
                    if _local(child.tag) == "meta" and child.attrib.get("name", "").lower() == "cover":
                        cover_id = child.attrib.get("content")
            if cover_id and manifest is not None:
                for item in manifest:
                    if _local(item.tag) == "item" and item.attrib.get("id") == cover_id:
                        href = item.attrib.get("href")
                        if href:
                            cover_path = posixpath.normpath(posixpath.join(opf_dir, href))
                            cover = {"path": cover_path, "media_type": item.attrib.get("media-type"), "source": "epub"}
                            break

            # EPUB3 books can mark the cover image with properties="cover-image".
            if cover is None and manifest is not None:
                for item in manifest:
                    if _local(item.tag) == "item" and "cover-image" in item.attrib.get("properties", "").split():
                        href = item.attrib.get("href")
                        if href:
                            cover_path = posixpath.normpath(posixpath.join(opf_dir, href))
                            cover = {"path": cover_path, "media_type": item.attrib.get("media-type"), "source": "epub"}
                            break
    except Exception as exc:
        candidate.errors.append(f"EPUB metadata: {type(exc).__name__}: {exc}")

    return evidence, cover
