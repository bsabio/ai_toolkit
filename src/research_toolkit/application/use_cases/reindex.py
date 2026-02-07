"""Use-case: Reindex – walk every stored resource, fix titles, rebuild library.jsonl."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from research_toolkit.application.ports import Indexer, Logger, Store
from research_toolkit.domain.entities import Resource
from research_toolkit.domain.value_objects import ResourceId


@dataclass
class ReindexResult:
    total: int = 0
    titles_fixed: int = 0
    errors: list[str] = field(default_factory=list)


class Reindex:
    """Rebuild the library index and fix titles using improved extraction logic."""

    def __init__(self, store: Store, indexer: Indexer, logger: Logger) -> None:
        self._store = store
        self._indexer = indexer
        self._log = logger

    def execute(self) -> ReindexResult:
        result = ReindexResult()
        base = self._store.base_path()
        resources_dir = os.path.join(base, "resources")
        if not os.path.isdir(resources_dir):
            return result

        # Collect all valid resources
        resources_with_content: list[tuple[Resource, str]] = []

        for rid_dir in sorted(os.listdir(resources_dir)):
            meta_path = os.path.join(resources_dir, rid_dir, "meta.json")
            content_path = os.path.join(resources_dir, rid_dir, "content.md")
            if not os.path.isfile(meta_path):
                continue

            result.total += 1
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                resource = Resource.from_dict(data)

                content = ""
                if os.path.isfile(content_path):
                    with open(content_path, "r", encoding="utf-8") as f:
                        content = f.read()

                # Re-extract title
                new_title = self._extract_title(content, resource.title)
                if new_title != resource.title:
                    old = resource.title
                    resource = Resource(
                        id=resource.id,
                        title=new_title,
                        url=resource.url,
                        captured_at=resource.captured_at,
                        content_hash=resource.content_hash,
                        tags=resource.tags,
                    )
                    # Write updated meta.json
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(resource.to_dict(), f, indent=2)
                    result.titles_fixed += 1
                    self._log.info(f"Fixed title [{resource.id}]: '{old}' → '{new_title}'")

                resources_with_content.append((resource, content))

            except Exception as exc:
                result.errors.append(f"{rid_dir}: {exc}")
                self._log.warning(f"Reindex error for {rid_dir}: {exc}")

        # Rebuild library.jsonl from scratch
        lib_path = os.path.join(base, "library.jsonl")
        with open(lib_path, "w", encoding="utf-8") as f:
            for resource, _ in resources_with_content:
                f.write(json.dumps(resource.to_dict()) + "\n")

        # Rebuild in-memory index
        # Reset internal state via a fresh load (the indexer re-reads from disk)
        self._indexer._index = {}  # type: ignore[attr-defined]
        self._indexer._resources = {}  # type: ignore[attr-defined]
        for resource, content in resources_with_content:
            self._indexer.index_resource(resource, content[:10000])

        self._log.info(
            f"Reindex complete: {result.total} resources, "
            f"{result.titles_fixed} titles fixed, {len(result.errors)} errors"
        )
        return result

    @staticmethod
    def _extract_title(content: str, fallback: str) -> str:
        """Same logic as IngestResource._extract_title – DRY candidate."""
        lines = content.split("\n")

        # --- Try YAML / TOML frontmatter first ---
        if lines and lines[0].strip() in ("---", "+++"):
            delimiter = lines[0].strip()
            for i, raw in enumerate(lines[1:], start=1):
                stripped = raw.strip()
                if stripped == delimiter:
                    break
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
