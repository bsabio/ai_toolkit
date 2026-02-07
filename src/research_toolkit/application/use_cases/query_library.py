"""Use-case: QueryLibrary – answer questions from the local library."""

from __future__ import annotations

from dataclasses import dataclass

from research_toolkit.application.ports import (
    Clock,
    Indexer,
    LLMProvider,
    Logger,
    SearchProvider,
    Snapshotter,
    Store,
)
from research_toolkit.application.use_cases.run_search import RunSearch, RunSearchRequest
from research_toolkit.domain.entities import Citation, Resource, SummaryOutput
from research_toolkit.domain.value_objects import ResourceId


@dataclass
class QueryRequest:
    question: str
    top_k: int = 5
    live: bool = False


@dataclass
class QueryResponse:
    answer: SummaryOutput
    sources: list[Resource]


class QueryLibrary:
    """Answer a question using the local library, with optional live fallback."""

    def __init__(
        self,
        store: Store,
        indexer: Indexer,
        llm: LLMProvider,
        search_provider: SearchProvider,
        snapshotter: Snapshotter,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._store = store
        self._indexer = indexer
        self._llm = llm
        self._search = search_provider
        self._snap = snapshotter
        self._clock = clock
        self._log = logger

    def execute(self, request: QueryRequest) -> QueryResponse:
        self._log.info(f"Query: {request.question!r} (top_k={request.top_k}, live={request.live})")

        # If --live, do a fresh search first
        if request.live:
            self._log.info("Live mode: performing fresh web search...")
            run_search = RunSearch(
                search_provider=self._search,
                snapshotter=self._snap,
                store=self._store,
                indexer=self._indexer,
                clock=self._clock,
                logger=self._log,
            )
            run_search.execute(RunSearchRequest(query=request.question, max_results=request.top_k))

        # Search local index
        resource_ids = self._indexer.search_local(request.question, top_k=request.top_k)

        if not resource_ids:
            return QueryResponse(
                answer=SummaryOutput(
                    text="No relevant resources found in the local library. "
                    "Try `tool search` first, or use `--live` to search the web.",
                    citations=[],
                ),
                sources=[],
            )

        # Gather context from stored resources
        sources: list[Resource] = []
        context_parts: list[str] = []
        citations: list[Citation] = []

        for rid in resource_ids:
            resource = self._store.load_resource(rid)
            if resource is None:
                continue
            content = self._store.load_content(rid) or ""
            # Truncate each source to keep prompt within model limits
            snippet = content[:1500]
            context_parts.append(
                f"--- Source [{resource.id}]: {resource.title} ---\n"
                f"URL: {resource.url}\n"
                f"Captured: {resource.captured_at}\n\n"
                f"{snippet}\n"
            )
            sources.append(resource)
            citations.append(
                Citation(
                    resource_id=rid,
                    resource_title=resource.title,
                    url=resource.url,
                    captured_at=resource.captured_at,
                    excerpt=snippet[:200],
                    local_path=f"research/resources/{rid}/content.md",
                )
            )

        combined_context = "\n\n".join(context_parts)

        prompt = (
            f"Answer the following question using ONLY the provided sources.\n"
            f"Cite sources using [source_id] notation.\n"
            f"If the sources don't contain enough information, say so.\n\n"
            f"Question: {request.question}\n\n"
            f"Sources:\n{combined_context}"
        )
        system = (
            "You are a research assistant. Answer questions using only the provided sources. "
            "Always cite your sources with their IDs. Be concise and factual."
        )

        answer_text = self._llm.complete(prompt, system=system, max_tokens=2000)

        return QueryResponse(
            answer=SummaryOutput(text=answer_text, citations=citations),
            sources=sources,
        )
