# Ebook Metadata

Conservative ebook metadata discovery and reconciliation pipeline.

The project is intentionally **read-only**. It discovers ebook candidates, collects evidence, reconciles metadata, and can optionally enrich the evidence with metadata returned by a separate Calibre container. It does **not** modify, move, delete, or import anything into Calibre.

## Evidence sources

- release folder / filename
- `.nfo`
- EPUB embedded metadata
- EPUB embedded cover
- external images next to the EPUB
- optional Calibre metadata enrichment

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
 local reconciliation
      |
      +--> optional Calibre lookup
      |       +--> ISBN
      |       +--> title + author
      |       +--> title
      |
      v
 final reconciliation
      |
      v
 JSON report + history
```

The pipeline is deliberately conservative: uncertain metadata remains `REVIEW` rather than being guessed.

## Running tests

```bash
docker compose run --rm test
```

## Docker scanner

The compose file mounts the source read-only. Set `RELEASES_PATH` to the path on the host containing the original release folders.

```bash
RELEASES_PATH=/path/to/releases docker compose run --rm scanner
```

## Calibre enrichment

Calibre enrichment is explicitly enabled with `--calibre` and uses the configured Calibre container without modifying its library.

```bash
docker compose run --rm scanner --calibre --calibre-container calibre-test
```

The current safeguards are:

- default Calibre command timeout: **15 seconds**
- default allowed metadata providers: **Google** and **Open Library**
- identical lookups are cached during one scan
- Calibre lookups run concurrently with a default maximum of **4 workers**
- worker count can be overridden with `--calibre-workers N` or `CALIBRE_WORKERS`
- timeout can be overridden with `CALIBRE_TIMEOUT`
- providers can be overridden with `CALIBRE_ALLOWED_PLUGINS`, as a comma-separated list

Example:

```bash
docker compose run --rm scanner --calibre --calibre-container calibre-test --calibre-workers 4
```

If a Calibre lookup fails or times out, the failure is recorded as enrichment evidence/error; the scanner continues and the local metadata remains available for reconciliation.

## Next stages

The planned pipeline continues with stronger metadata reconciliation, AI-assisted identification using Qwen3-VL where local evidence is insufficient, duplicate detection, and finally a review UI. AI should be used as an additional evidence source rather than silently replacing deterministic metadata.
