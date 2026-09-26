# Ebook Metadata

First vertical slice of the ebook/Calibre metadata project.

The project is intentionally read-only and conservative. This stage only discovers ebook candidates and collects evidence from:

- release folder / filename
- `.nfo`
- EPUB embedded metadata
- EPUB embedded cover
- external images next to the EPUB

It does **not** modify, move, delete, or import anything into Calibre.

## Design

```text
release folders
      |
      v
 discovery
      |
      +--> folder/filename evidence
      +--> NFO evidence
      +--> EPUB metadata evidence
      +--> cover evidence
      |
      v
 JSON report
```

Later stages will add reconciliation, Calibre identification/enrichment, Qwen3-VL, duplicate detection, and finally the web UI.

## Running locally

```bash
python -m ebook_metadata.scanner --source /data/releases --output /data/output/inventory.json
```

## Docker

The compose file mounts the source read-only. Set `RELEASES_PATH` to the path on the host containing the original release folders.

```bash
RELEASES_PATH=/path/to/releases docker compose run --rm scanner
```
