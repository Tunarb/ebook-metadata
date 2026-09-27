FROM docker:29.7.2-cli AS docker-cli

FROM python:3.12-slim

WORKDIR /app

# The runtime container uses the host Docker socket to invoke the existing
# Calibre container. The Docker daemon itself is NOT started here.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN pip install --no-cache-dir ".[dev]"

ENTRYPOINT ["ebook-scan"]
