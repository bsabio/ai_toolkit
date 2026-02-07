"""Domain entities – core business objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_toolkit.domain.value_objects import (
    ContentHash,
    ResourceId,
    Timestamp,
    Url,
)


@dataclass
class Resource:
    """A captured web resource stored in the local library."""

    id: ResourceId
    title: str
    url: Url
    captured_at: Timestamp
    content_hash: ContentHash
    tags: list[str] = field(default_factory=list)
    snippet_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "title": self.title,
            "url": str(self.url),
            "captured_at": self.captured_at.iso(),
            "content_hash": str(self.content_hash),
            "tags": self.tags,
            "snippet_count": self.snippet_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Resource":
        return cls(
            id=ResourceId(d["id"]),
            title=d["title"],
            url=Url(d["url"]),
            captured_at=Timestamp.from_iso(d["captured_at"]),
            content_hash=ContentHash(d["content_hash"]),
            tags=d.get("tags", []),
            snippet_count=d.get("snippet_count", 0),
        )


@dataclass
class Citation:
    """A citation pointing to a specific resource and location."""

    resource_id: ResourceId
    resource_title: str
    url: Url
    captured_at: Timestamp
    excerpt: str
    local_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": str(self.resource_id),
            "resource_title": self.resource_title,
            "url": str(self.url),
            "captured_at": self.captured_at.iso(),
            "excerpt": self.excerpt,
            "local_path": self.local_path,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Citation":
        return cls(
            resource_id=ResourceId(d["resource_id"]),
            resource_title=d["resource_title"],
            url=Url(d["url"]),
            captured_at=Timestamp.from_iso(d["captured_at"]),
            excerpt=d["excerpt"],
            local_path=d.get("local_path", ""),
        )


@dataclass
class SearchResult:
    """A single result from a web search (before ingestion)."""

    title: str
    url: str
    snippet: str
    position: int = 0


@dataclass
class ResearchSession:
    """A research session grouping queries, results, and outputs."""

    session_id: str
    created_at: Timestamp
    queries: list[str] = field(default_factory=list)
    resource_ids: list[ResourceId] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.iso(),
            "queries": self.queries,
            "resource_ids": [str(r) for r in self.resource_ids],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ResearchSession":
        return cls(
            session_id=d["session_id"],
            created_at=Timestamp.from_iso(d["created_at"]),
            queries=d.get("queries", []),
            resource_ids=[ResourceId(r) for r in d.get("resource_ids", [])],
        )


@dataclass
class SummaryOutput:
    """A generated summary with citations."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    format: str = "md"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "format": self.format,
        }
