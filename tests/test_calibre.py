from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ebook_metadata.calibre.client import (
    CalibreClient,
    CalibreLookupError,
    parse_opf,
)


POLLi_OPF = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier opf:scheme="calibre">internal-calibre-id</dc:identifier>
    <dc:identifier opf:scheme="uuid">internal-uuid</dc:identifier>
    <dc:title>Polli 2 - Det er fint at være til</dc:title>
    <dc:creator opf:file-as="Unknown" opf:role="aut">Guus Kuijer</dc:creator>
    <dc:creator opf:role="edt">Editor Person</dc:creator>
    <dc:date>2013-05-27T13:08:29+00:00</dc:date>
    <dc:description>&lt;p&gt;Beskrivelse.&lt;/p&gt;</dc:description>
    <dc:publisher>Lindhardt og Ringhof</dc:publisher>
    <dc:identifier opf:scheme="GOOGLE">dRQnqKQe6L0C</dc:identifier>
    <dc:identifier opf:scheme="ISBN">9788711378069</dc:identifier>
    <dc:language>dan</dc:language>
    <dc:language>dan</dc:language>
    <dc:subject>Juvenile Fiction</dc:subject>
    <dc:subject>Family</dc:subject>
    <meta name="calibre:series" content="Polleke"/>
    <meta name="calibre:series_index" content="2"/>
  </metadata>
</package>
"""


ALI_OPF = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Ali på mål</dc:title>
    <dc:creator opf:role="aut">Unknown</dc:creator>
    <dc:publisher>Turbine Forlaget</dc:publisher>
    <dc:identifier opf:scheme="ISBN">9788740697445</dc:identifier>
  </metadata>
</package>
"""


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(["docker"], returncode, stdout, stderr)


def test_parse_opf_extracts_metadata_and_ignores_unknown_author():
    result = parse_opf(POLLi_OPF)

    assert result.title == "Polli 2 - Det er fint at være til"
    assert result.authors == ["Guus Kuijer"]
    assert result.publisher == "Lindhardt og Ringhof"
    assert result.published == "2013-05-27T13:08:29+00:00"
    assert result.description == "<p>Beskrivelse.</p>"
    assert result.languages == ["dan"]
    assert result.subjects == ["Juvenile Fiction", "Family"]
    assert result.series == "Polleke"
    assert result.series_index == 2.0
    assert result.identifiers == {
        "google": "dRQnqKQe6L0C",
        "isbn": "9788711378069",
    }


def test_parse_opf_keeps_unknown_as_missing_author():
    result = parse_opf(ALI_OPF)

    assert result.title == "Ali på mål"
    assert result.authors == []
    assert result.publisher == "Turbine Forlaget"
    assert result.identifiers["isbn"] == "9788740697445"


def test_lookup_builds_expected_docker_command(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return completed(POLLi_OPF)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CalibreClient(container="calibre-test").lookup(
        title="Polli 2 - Det er fint at være til",
        authors=["Guus Kuijer"],
        isbn="9788711378069",
    )

    assert result.authors == ["Guus Kuijer"]
    args, kwargs = calls[0]
    assert args[:5] == ["docker", "exec", "calibre-test", "fetch-ebook-metadata", "--title"]
    assert "Polli 2 - Det er fint at være til" in args
    assert "--authors" in args
    assert "Guus Kuijer" in args
    assert "--isbn" in args
    assert "9788711378069" in args
    assert "--timeout" in args
    assert args[-1] == "--opf"
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_lookup_joins_multiple_authors_and_allowed_plugins(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return completed(POLLi_OPF)

    monkeypatch.setattr(subprocess, "run", fake_run)

    CalibreClient(allowed_plugins=["Google", "Open Library"]).lookup(
        title="Test", authors=["Author One", "Author Two"]
    )

    args = calls[0]
    assert args[args.index("--authors") + 1] == "Author One & Author Two"
    assert args.count("--allowed-plugin") == 2
    assert "Google" in args
    assert "Open Library" in args


def test_lookup_requires_input():
    with pytest.raises(ValueError, match="At least one metadata lookup value"):
        CalibreClient().lookup()


def test_lookup_reports_calibre_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            2, args[0], stderr="metadata lookup failed"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(CalibreLookupError, match="metadata lookup failed"):
        CalibreClient().lookup(isbn="9788726932195")


def test_lookup_reports_empty_opf(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed("", "no result"))

    with pytest.raises(CalibreLookupError, match="no result"):
        CalibreClient().lookup(title="No such book")


def test_lookup_reports_malformed_opf(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed("<not-opf"))

    with pytest.raises(CalibreLookupError, match="Could not parse Calibre OPF"):
        CalibreClient().lookup(title="Broken")


def test_cover_download_copies_from_container(monkeypatch, tmp_path: Path):
    calls = []
    destination = tmp_path / "cover.jpg"

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:4] == ["docker", "exec", "calibre", "fetch-ebook-metadata"]:
            return completed("Cover               : /tmp/fake-cover.jpg\n")
        if args[:2] == ["docker", "cp"]:
            destination.write_bytes(b"jpeg-data")
            return completed()
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CalibreClient().download_cover(
        destination=destination,
        isbn="9788726932195",
    )

    assert result == destination
    assert destination.read_bytes() == b"jpeg-data"
    assert calls[0][0:4] == ["docker", "exec", "calibre", "fetch-ebook-metadata"]
    assert "--cover" in calls[0]
    assert calls[1][:2] == ["docker", "cp"]
    assert calls[2][0:4] == ["docker", "exec", "calibre", "rm"]
