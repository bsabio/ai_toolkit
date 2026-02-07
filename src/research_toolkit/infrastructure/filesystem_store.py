"""Infrastructure: Filesystem store – persists resources under ./research/."""

from __future__ import annotations

import json
import os
from typing import Any

from research_toolkit.application.ports import Store as StorePort
from research_toolkit.domain.entities import Resource
from research_toolkit.domain.value_objects import ResourceId


class FilesystemStore(StorePort):
    """Stores resources and sessions on local disk under a base directory."""

    def __init__(self, base: str = "research") -> None:
        self._base = os.path.abspath(base)

    # ---- paths ----

    def base_path(self) -> str:
        return self._base

    def _resource_dir(self, rid: ResourceId) -> str:
        return os.path.join(self._base, "resources", str(rid))

    def _session_dir(self, session_id: str) -> str:
        return os.path.join(self._base, "sessions", session_id)

    def _library_path(self) -> str:
        return os.path.join(self._base, "library.jsonl")

    # ---- public api ----

    def ensure_dirs(self) -> None:
        for sub in ["resources", "sessions", "reviews"]:
            os.makedirs(os.path.join(self._base, sub), exist_ok=True)

    def save_resource(self, resource: Resource, content_md: str, raw_html: str | None = None) -> None:
        rdir = self._resource_dir(resource.id)
        os.makedirs(rdir, exist_ok=True)
        raw_dir = os.path.join(rdir, "raw")
        os.makedirs(raw_dir, exist_ok=True)

        # meta.json
        with open(os.path.join(rdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(resource.to_dict(), f, indent=2)

        # content.md
        with open(os.path.join(rdir, "content.md"), "w", encoding="utf-8") as f:
            f.write(content_md)

        # snippets.json (initially empty)
        snippets_path = os.path.join(rdir, "snippets.json")
        if not os.path.exists(snippets_path):
            with open(snippets_path, "w", encoding="utf-8") as f:
                json.dump([], f)

        # raw snapshot
        if raw_html:
            with open(os.path.join(raw_dir, "snapshot.html"), "w", encoding="utf-8") as f:
                f.write(raw_html)

        # Append to library.jsonl
        self._append_to_library(resource)

    def load_resource(self, resource_id: ResourceId) -> Resource | None:
        meta_path = os.path.join(self._resource_dir(resource_id), "meta.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            return Resource.from_dict(json.load(f))

    def load_content(self, resource_id: ResourceId) -> str | None:
        content_path = os.path.join(self._resource_dir(resource_id), "content.md")
        if not os.path.exists(content_path):
            return None
        with open(content_path, "r", encoding="utf-8") as f:
            return f.read()

    def resource_exists(self, resource_id: ResourceId) -> bool:
        return os.path.exists(os.path.join(self._resource_dir(resource_id), "meta.json"))

    def save_snippets(self, resource_id: ResourceId, snippets: list[dict[str, Any]]) -> None:
        rdir = self._resource_dir(resource_id)
        os.makedirs(rdir, exist_ok=True)
        with open(os.path.join(rdir, "snippets.json"), "w", encoding="utf-8") as f:
            json.dump(snippets, f, indent=2)

    def load_snippets(self, resource_id: ResourceId) -> list[dict[str, Any]]:
        path = os.path.join(self._resource_dir(resource_id), "snippets.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def save_session(self, session_id: str, data: dict[str, Any]) -> None:
        sdir = self._session_dir(session_id)
        os.makedirs(sdir, exist_ok=True)
        os.makedirs(os.path.join(sdir, "outputs"), exist_ok=True)

        with open(os.path.join(sdir, "queries.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_session_output(self, session_dir: str, filename: str, content: str) -> None:
        sdir = self._session_dir(session_dir)
        outdir = os.path.join(sdir, "outputs")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, filename), "w", encoding="utf-8") as f:
            f.write(content)

    # ---- private ----

    def _append_to_library(self, resource: Resource) -> None:
        lib_path = self._library_path()
        os.makedirs(os.path.dirname(lib_path), exist_ok=True)
        with open(lib_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(resource.to_dict()) + "\n")
