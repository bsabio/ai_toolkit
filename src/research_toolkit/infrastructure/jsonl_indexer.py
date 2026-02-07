"""Infrastructure: JSONL-based indexer for the local library.

Uses a simple JSONL registry + in-memory keyword search for v1.
Can be upgraded to SQLite FTS in a future iteration.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter

from research_toolkit.application.ports import Indexer as IndexerPort
from research_toolkit.domain.entities import Resource
from research_toolkit.domain.value_objects import ResourceId


class JsonlIndexer(IndexerPort):
    """In-memory keyword index backed by library.jsonl for persistence."""

    def __init__(self, library_path: str = "research/library.jsonl") -> None:
        self._library_path = os.path.abspath(library_path)
        # Derive resources dir from library path
        self._resources_dir = os.path.join(os.path.dirname(self._library_path), "resources")
        # In-memory inverted index: term -> {resource_id: count}
        self._index: dict[str, Counter[str]] = {}
        self._resources: dict[str, Resource] = {}
        self._load()

    # ---- public api ----

    def index_resource(self, resource: Resource, content: str) -> None:
        rid = str(resource.id)
        self._resources[rid] = resource
        terms = self._tokenize(f"{resource.title} {content}")
        for term in terms:
            if term not in self._index:
                self._index[term] = Counter()
            self._index[term][rid] += 1

    def search_local(self, query: str, top_k: int = 5) -> list[ResourceId]:
        terms = self._tokenize(query)
        scores: Counter[str] = Counter()
        for term in terms:
            if term in self._index:
                for rid, count in self._index[term].items():
                    scores[rid] += count

        # Return top-k by score
        top = scores.most_common(top_k)
        return [ResourceId(rid) for rid, _ in top]

    def list_all(self) -> list[Resource]:
        return list(self._resources.values())

    def remove(self, resource_id: ResourceId) -> None:
        rid = str(resource_id)
        self._resources.pop(rid, None)
        for term_counter in self._index.values():
            term_counter.pop(rid, None)

    def healthy(self) -> bool:
        return True  # JSONL indexer is always healthy if we reach this point

    # ---- private ----

    def _load(self) -> None:
        """Load entries from the JSONL library file and index stored content."""
        if not os.path.exists(self._library_path):
            return
        seen_ids: set[str] = set()
        with open(self._library_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    resource = Resource.from_dict(data)
                    rid = str(resource.id)
                    if rid in seen_ids:
                        continue  # dedupe
                    seen_ids.add(rid)
                    self._resources[rid] = resource

                    # Try to load stored content for full-text indexing
                    content = ""
                    content_path = os.path.join(self._resources_dir, rid, "content.md")
                    if os.path.exists(content_path):
                        try:
                            with open(content_path, "r", encoding="utf-8") as cf:
                                content = cf.read()[:10000]  # cap to avoid huge memory
                        except Exception:
                            pass

                    terms = self._tokenize(f"{resource.title} {content}")
                    for term in terms:
                        if term not in self._index:
                            self._index[term] = Counter()
                        self._index[term][rid] += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace tokenizer with lowercasing and stopword removal."""
        stops = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "it"}
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [w for w in words if w not in stops and len(w) > 1]
