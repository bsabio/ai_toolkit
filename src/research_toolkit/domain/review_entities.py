"""Domain entities for artifact review – pure data, no IO."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Issue severity levels, ordered from most to least critical."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        order = [Severity.CRITICAL, Severity.MAJOR, Severity.MINOR, Severity.SUGGESTION]
        return order.index(self) < order.index(other)


@dataclass
class ReviewIssue:
    """A single issue found during artifact review."""

    severity: Severity
    title: str
    location: str
    evidence: str
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "title": self.title,
            "location": self.location,
            "evidence": self.evidence,
            "fix": self.fix,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewIssue":
        return cls(
            severity=Severity(d["severity"]),
            title=d["title"],
            location=d.get("location", ""),
            evidence=d.get("evidence", ""),
            fix=d.get("fix", ""),
        )


@dataclass
class ArtifactRef:
    """Reference to the artifact being reviewed."""

    path: str
    filename: str
    mime_type: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactRef":
        return cls(
            path=d["path"],
            filename=d["filename"],
            mime_type=d["mime_type"],
            size_bytes=d.get("size_bytes", 0),
        )


@dataclass
class ReviewReport:
    """Structured review report produced by the reviewer."""

    overall_score: int  # 0-100
    passed: bool
    summary: str
    issues: list[ReviewIssue] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    artifact: ArtifactRef | None = None
    model: str = ""
    reviewed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "overall_score": self.overall_score,
            "pass": self.passed,
            "summary": self.summary,
            "issues": [i.to_dict() for i in self.issues],
            "next_steps": self.next_steps,
        }
        if self.artifact:
            d["artifact"] = self.artifact.to_dict()
        if self.model:
            d["model"] = self.model
        if self.reviewed_at:
            d["reviewed_at"] = self.reviewed_at
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewReport":
        return cls(
            overall_score=d.get("overall_score", 0),
            passed=d.get("pass", d.get("passed", False)),
            summary=d.get("summary", ""),
            issues=[ReviewIssue.from_dict(i) for i in d.get("issues", [])],
            next_steps=d.get("next_steps", []),
            artifact=ArtifactRef.from_dict(d["artifact"]) if d.get("artifact") else None,
            model=d.get("model", ""),
            reviewed_at=d.get("reviewed_at", ""),
        )
