"""Use-case: SummarizeResource – generate a summary with citations."""

from __future__ import annotations

from dataclasses import dataclass

from research_toolkit.application.ports import Indexer, LLMProvider, Logger, Store
from research_toolkit.domain.entities import Citation, Resource, SummaryOutput
from research_toolkit.domain.value_objects import ResourceId


@dataclass
class SummarizeRequest:
    resource_id: str
    format: str = "md"  # "md" or "json"


@dataclass
class SummarizeResponse:
    summary: SummaryOutput
    resource: Resource


class SummarizeResource:
    """Summarize a stored resource with citations."""

    def __init__(
        self,
        store: Store,
        indexer: Indexer,
        llm: LLMProvider,
        logger: Logger,
    ) -> None:
        self._store = store
        self._indexer = indexer
        self._llm = llm
        self._log = logger

    def execute(self, request: SummarizeRequest) -> SummarizeResponse:
        rid = ResourceId(request.resource_id)

        resource = self._store.load_resource(rid)
        if resource is None:
            raise ValueError(f"Resource not found: {request.resource_id}")

        content = self._store.load_content(rid)
        if not content:
            raise ValueError(f"No content stored for resource: {request.resource_id}")

        self._log.info(f"Summarizing [{rid}]: {resource.title}")

        # Truncate content for LLM context
        max_chars = 12_000
        truncated = content[:max_chars]
        if len(content) > max_chars:
            truncated += "\n\n[... content truncated ...]"

        prompt = (
            f"Summarize the following document. Include key facts and findings.\n"
            f"After the summary, list 2-5 key quotes from the text as citations.\n"
            f"Format each citation as: [CITE] \"exact quote\" (source)\n\n"
            f"Document title: {resource.title}\n"
            f"Source: {resource.url}\n\n"
            f"---\n{truncated}\n---"
        )

        system = (
            "You are a research assistant. Produce concise, factual summaries. "
            "Always include verifiable citations from the source text."
        )

        raw_summary = self._llm.complete(prompt, system=system, max_tokens=1500)

        # Build citations
        citations = [
            Citation(
                resource_id=rid,
                resource_title=resource.title,
                url=resource.url,
                captured_at=resource.captured_at,
                excerpt=raw_summary[:200],
                local_path=f"research/resources/{rid}/content.md",
            )
        ]

        summary = SummaryOutput(
            text=raw_summary,
            citations=citations,
            format=request.format,
        )

        return SummarizeResponse(summary=summary, resource=resource)
