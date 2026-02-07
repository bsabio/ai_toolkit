"""Domain value objects – small immutable types with validation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ResourceId:
    """Stable, deterministic identifier for a resource (8-char hex digest of URL)."""

    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{8,16}", self.value):
            raise ValueError(f"Invalid ResourceId: {self.value!r}")

    @classmethod
    def from_url(cls, url: str) -> "ResourceId":
        digest = hashlib.sha256(url.encode()).hexdigest()[:12]
        return cls(value=digest)

    @classmethod
    def from_content(cls, content: str) -> "ResourceId":
        digest = hashlib.sha256(content.encode()).hexdigest()[:12]
        return cls(value=digest)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Url:
    """Validated URL value object."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith(("http://", "https://", "file://")):
            raise ValueError(f"Invalid URL: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Timestamp:
    """UTC timestamp value object."""

    dt: datetime

    @classmethod
    def now(cls) -> "Timestamp":
        return cls(dt=datetime.now(timezone.utc))

    @classmethod
    def from_iso(cls, iso: str) -> "Timestamp":
        return cls(dt=datetime.fromisoformat(iso))

    def iso(self) -> str:
        return self.dt.isoformat()

    def __str__(self) -> str:
        return self.iso()


@dataclass(frozen=True)
class ContentHash:
    """SHA-256 hash of content for dedup."""

    value: str

    @classmethod
    def of(cls, text: str) -> "ContentHash":
        return cls(value=hashlib.sha256(text.encode()).hexdigest())

    def __str__(self) -> str:
        return self.value
