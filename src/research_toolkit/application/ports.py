"""Application ports – abstract interfaces that infrastructure must implement.

These are the boundaries of the application layer. Domain and application code
depend only on these abstractions, never on concrete infrastructure.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

from research_toolkit.domain.entities import Resource, SearchResult
from research_toolkit.domain.value_objects import ResourceId, Timestamp


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchProvider(abc.ABC):
    """Port: web search engine."""

    @abc.abstractmethod
    def search(
        self, query: str, *, max_results: int = 10, recency_days: int | None = None
    ) -> list[SearchResult]:
        ...


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
class LLMProvider(abc.ABC):
    """Port: large-language-model completions."""

    @abc.abstractmethod
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2048) -> str:
        ...


class MultimodalLLMProvider(abc.ABC):
    """Port: multimodal LLM that accepts text + file attachments.

    Attachments are a list of dicts: ``{"mime_type": str, "data": bytes}``.
    """

    @abc.abstractmethod
    def complete_multimodal(
        self,
        prompt: str,
        attachments: list[dict[str, Any]],
        *,
        system: str = "",
        max_tokens: int = 4096,
        thinking: str | None = None,
    ) -> str:
        ...


# ---------------------------------------------------------------------------
# Store (file I/O)
# ---------------------------------------------------------------------------
class Store(abc.ABC):
    """Port: persistent resource storage."""

    @abc.abstractmethod
    def save_resource(self, resource: Resource, content_md: str, raw_html: str | None = None) -> None:
        ...

    @abc.abstractmethod
    def load_resource(self, resource_id: ResourceId) -> Resource | None:
        ...

    @abc.abstractmethod
    def load_content(self, resource_id: ResourceId) -> str | None:
        ...

    @abc.abstractmethod
    def resource_exists(self, resource_id: ResourceId) -> bool:
        ...

    @abc.abstractmethod
    def save_snippets(self, resource_id: ResourceId, snippets: list[dict[str, Any]]) -> None:
        ...

    @abc.abstractmethod
    def load_snippets(self, resource_id: ResourceId) -> list[dict[str, Any]]:
        ...

    @abc.abstractmethod
    def save_session(self, session_dir: str, data: dict[str, Any]) -> None:
        ...

    @abc.abstractmethod
    def save_session_output(self, session_dir: str, filename: str, content: str) -> None:
        ...

    @abc.abstractmethod
    def ensure_dirs(self) -> None:
        ...

    @abc.abstractmethod
    def base_path(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Snapshotter (HTML/PDF capture)
# ---------------------------------------------------------------------------
class Snapshotter(abc.ABC):
    """Port: capture raw page snapshots."""

    @abc.abstractmethod
    def capture(self, url: str) -> tuple[str | None, str | None]:
        """Return (extracted_text, raw_html). Either may be None on failure."""
        ...


# ---------------------------------------------------------------------------
# Indexer (search over local library)
# ---------------------------------------------------------------------------
class Indexer(abc.ABC):
    """Port: index & search the local resource library."""

    @abc.abstractmethod
    def index_resource(self, resource: Resource, content: str) -> None:
        ...

    @abc.abstractmethod
    def search_local(self, query: str, top_k: int = 5) -> list[ResourceId]:
        ...

    @abc.abstractmethod
    def list_all(self) -> list[Resource]:
        ...

    @abc.abstractmethod
    def remove(self, resource_id: ResourceId) -> None:
        ...

    @abc.abstractmethod
    def healthy(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------
class Clock(abc.ABC):
    """Port: provides current time (makes testing deterministic)."""

    @abc.abstractmethod
    def now(self) -> Timestamp:
        ...


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
class Logger(abc.ABC):
    """Port: structured logging with secret redaction."""

    @abc.abstractmethod
    def info(self, msg: str, **kw: Any) -> None:
        ...

    @abc.abstractmethod
    def warn(self, msg: str, **kw: Any) -> None:
        ...

    @abc.abstractmethod
    def error(self, msg: str, **kw: Any) -> None:
        ...

    @abc.abstractmethod
    def debug(self, msg: str, **kw: Any) -> None:
        ...
