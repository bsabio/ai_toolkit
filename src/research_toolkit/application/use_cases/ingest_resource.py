"""Use-case: IngestResource – ingest a URL or local file into the library."""

from __future__ import annotations

import os
from dataclasses import dataclass

from research_toolkit.application.ports import Clock, Indexer, Logger, Snapshotter, Store
from research_toolkit.domain.entities import Resource
from research_toolkit.domain.value_objects import ContentHash, ResourceId, Url


@dataclass
class IngestRequest:
    path_or_url: str


@dataclass
class IngestResponse:
    resource: Resource
    already_existed: bool = False


class IngestResource:
    """Ingest a URL or local file into the research library."""

    def __init__(
        self,
        snapshotter: Snapshotter,
        store: Store,
        indexer: Indexer,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._snap = snapshotter
        self._store = store
        self._indexer = indexer
        self._clock = clock
        self._log = logger

    def execute(self, request: IngestRequest) -> IngestResponse:
        source = request.path_or_url
        is_url = source.startswith(("http://", "https://"))

        if is_url:
            rid = ResourceId.from_url(source)
            if self._store.resource_exists(rid):
                existing = self._store.load_resource(rid)
                if existing:
                    self._log.info(f"Resource already exists: {rid}")
                    return IngestResponse(resource=existing, already_existed=True)

            text, raw_html = self._snap.capture(source)
            content_md = text or ""
            url = Url(source)
            title = self._extract_title(content_md, source)
        else:
            # Local file
            if not os.path.exists(source):
                raise FileNotFoundError(f"File not found: {source}")
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                content_md = f.read()
            raw_html = None
            rid = ResourceId.from_content(content_md)
            if self._store.resource_exists(rid):
                existing = self._store.load_resource(rid)
                if existing:
                    return IngestResponse(resource=existing, already_existed=True)
            url = Url(f"file://{os.path.abspath(source)}")
            title = os.path.basename(source)

        if not content_md.strip():
            raise ValueError("No content could be extracted from the source.")

        ts = self._clock.now()
        chash = ContentHash.of(content_md)

        resource = Resource(
            id=rid,
            title=title,
            url=url,
            captured_at=ts,
            content_hash=chash,
            tags=[],
        )

        self._store.save_resource(resource, content_md, raw_html)
        self._indexer.index_resource(resource, content_md)
        self._log.info(f"Ingested [{rid}]: {title}")

        return IngestResponse(resource=resource)

    @staticmethod
    def _extract_title(content: str, fallback: str) -> str:
        lines = content.split("\n")

        # --- Try YAML / TOML frontmatter first ---
        if lines and lines[0].strip() in ("---", "+++"):
            delimiter = lines[0].strip()
            for i, raw in enumerate(lines[1:], start=1):
                stripped = raw.strip()
                if stripped == delimiter:
                    break  # end of frontmatter
                if stripped.lower().startswith("title:"):
                    val = stripped.split(":", 1)[1].strip().strip("'\"")
                    if val:
                        return val
            # After frontmatter, search body for heading
            body_start = 0
            for i, raw in enumerate(lines[1:], start=1):
                if raw.strip() == delimiter:
                    body_start = i + 1
                    break
            for raw in lines[body_start:]:
                stripped = raw.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
                if stripped and not stripped.startswith(("---", "+++")) and len(stripped) < 200:
                    return stripped

        # --- No frontmatter: first heading or first short line ---
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and len(stripped) < 200:
                return stripped

        return fallback
