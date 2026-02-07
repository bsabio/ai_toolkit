"""Infrastructure: Wall-clock implementation."""

from __future__ import annotations

from research_toolkit.application.ports import Clock as ClockPort
from research_toolkit.domain.value_objects import Timestamp


class WallClock(ClockPort):
    """Real wall-clock time."""

    def now(self) -> Timestamp:
        return Timestamp.now()
