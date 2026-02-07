"""Use-case: RunSearch – search the web, ingest results, create a session."""

from __future__ import annotations

import re
from dataclasses import dataclass

from research_toolkit.application.ports import (
    Clock,
    Indexer,
    Logger,
    SearchProvider,
    Snapshotter,
    Store,
)
from research_toolkit.domain.entities import Resource, ResearchSession, SearchResult
from research_toolkit.domain.value_objects import ContentHash, ResourceId, Url


@dataclass
class RunSearchRequest:
    query: str
    max_results: int = 10
    recency_days: int | None = None


@dataclass
class RunSearchResponse:
    session: ResearchSession
    resources: list[Resource]
    skipped: int = 0


class RunSearch:
    """Orchestrates web search → snapshot → store → index."""

    def __init__(
        self,
        search_provider: SearchProvider,
        snapshotter: Snapshotter,
        store: Store,
        indexer: Indexer,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._search = search_provider
        self._snap = snapshotter
        self._store = store
        self._indexer = indexer
        self._clock = clock
        self._log = logger

    def execute(self, request: RunSearchRequest) -> RunSearchResponse:
        self._log.info(f"Searching: {request.query!r} (max={request.max_results})")

        results: list[SearchResult] = self._search.search(
            request.query,
            max_results=request.max_results,
            recency_days=request.recency_days,
        )

        ts = self._clock.now()
        slug = re.sub(r"[^a-z0-9]+", "_", request.query.lower())[:40].strip("_")
        session_id = f"{ts.dt.strftime('%Y%m%dT%H%M%S')}__{slug}"
        session = ResearchSession(session_id=session_id, created_at=ts, queries=[request.query])

        resources: list[Resource] = []
        skipped = 0

        for i, sr in enumerate(results):
            try:
                rid = ResourceId.from_url(sr.url)

                # Dedupe
                if self._store.resource_exists(rid):
                    self._log.info(f"  skip (exists): {sr.url}")
                    session.resource_ids.append(rid)
                    existing = self._store.load_resource(rid)
                    if existing:
                        resources.append(existing)
                    skipped += 1
                    continue

                # Snapshot
                text, raw_html = self._snap.capture(sr.url)
                content_md = text or sr.snippet or ""
                if not content_md.strip():
                    self._log.warn(f"  skip (empty): {sr.url}")
                    skipped += 1
                    continue

                chash = ContentHash.of(content_md)

                resource = Resource(
                    id=rid,
                    title=sr.title,
                    url=Url(sr.url),
                    captured_at=ts,
                    content_hash=chash,
                    tags=[],
                )

                self._store.save_resource(resource, content_md, raw_html)
                self._indexer.index_resource(resource, content_md)
                session.resource_ids.append(rid)
                resources.append(resource)
                self._log.info(f"  stored [{rid}]: {sr.title}")
            except Exception as exc:
                self._log.error(f"  failed for {sr.url}: {exc}")
                skipped += 1

        # Persist session
        self._store.save_session(
            session_id,
            {
                "session": session.to_dict(),
                "queries": [request.query],
                "result_count": len(resources),
                "skipped": skipped,
            },
        )

        return RunSearchResponse(session=session, resources=resources, skipped=skipped)
