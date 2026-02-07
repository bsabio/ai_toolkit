"""Use-case: ListResources – list all resources in the local library."""

from __future__ import annotations

from dataclasses import dataclass

from research_toolkit.application.ports import Indexer, Logger
from research_toolkit.domain.entities import Resource


@dataclass
class ListResponse:
    resources: list[Resource]
    total: int


class ListResources:
    """List all stored resources."""

    def __init__(self, indexer: Indexer, logger: Logger) -> None:
        self._indexer = indexer
        self._log = logger

    def execute(self) -> ListResponse:
        resources = self._indexer.list_all()
        self._log.info(f"Found {len(resources)} resources in library.")
        return ListResponse(resources=resources, total=len(resources))
