"""Use-case: ReviewArtifact – multimodal artifact feedback via LLM."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Any

from research_toolkit.application.ports import Clock, Logger, MultimodalLLMProvider, Store
from research_toolkit.domain.review_entities import (
    ArtifactRef,
    ReviewIssue,
    ReviewReport,
    Severity,
)


# ---------------------------------------------------------------------------
# MIME helpers (shared utility)
# ---------------------------------------------------------------------------
SUPPORTED_MIMES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
    ".svg": "image/svg+xml",
}


def detect_mime(path: str) -> str:
    """Detect MIME type from file extension, falling back to mimetypes stdlib."""
    ext = os.path.splitext(path)[1].lower()
    if ext in SUPPORTED_MIMES:
        return SUPPORTED_MIMES[ext]
    guess, _ = mimetypes.guess_type(path)
    return guess or "application/octet-stream"


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------
@dataclass
class ReviewRequest:
    artifact_path: str
    rubric_path: str | None = None
    output_format: str = "json"  # "json" or "md"
    model: str | None = None
    thinking: str | None = None  # "high" or "low"


@dataclass
class ReviewResponse:
    report: ReviewReport
    review_dir: str  # path where output was stored
    report_json: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Default rubric (used when none is provided)
# ---------------------------------------------------------------------------
DEFAULT_RUBRIC: dict[str, Any] = {
    "name": "general",
    "description": "General-purpose artifact quality review",
    "pass_threshold": 60,
    "criteria": [
        {"name": "Clarity", "weight": 25, "description": "Is the content clear and easy to understand?"},
        {"name": "Completeness", "weight": 25, "description": "Does the artifact cover all necessary information?"},
        {"name": "Correctness", "weight": 25, "description": "Is the content accurate and free of errors?"},
        {"name": "Presentation", "weight": 25, "description": "Is the artifact well-formatted and visually coherent?"},
    ],
}


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------
class ReviewArtifact:
    """Review an artifact file using a multimodal LLM and return structured feedback."""

    def __init__(
        self,
        llm: MultimodalLLMProvider,
        store: Store,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._llm = llm
        self._store = store
        self._clock = clock
        self._log = logger

    def execute(self, request: ReviewRequest) -> ReviewResponse:
        # 1. Validate artifact exists
        artifact_path = os.path.abspath(request.artifact_path)
        if not os.path.isfile(artifact_path):
            raise FileNotFoundError(f"Artifact not found: {request.artifact_path}")

        mime = detect_mime(artifact_path)
        file_size = os.path.getsize(artifact_path)
        filename = os.path.basename(artifact_path)

        self._log.info(f"Reviewing artifact: {filename} ({mime}, {file_size:,} bytes)")

        artifact_ref = ArtifactRef(
            path=artifact_path,
            filename=filename,
            mime_type=mime,
            size_bytes=file_size,
        )

        # 2. Load rubric
        rubric = self._load_rubric(request.rubric_path)

        # 3. Read file bytes
        with open(artifact_path, "rb") as f:
            file_bytes = f.read()

        # 4. Build attachments
        attachments: list[dict[str, Any]] = []

        # For text-based files, include as text in the prompt instead
        text_content: str | None = None
        if mime.startswith("text/") or mime in ("application/json", "application/csv"):
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

        if text_content is None:
            # Binary attachment (image or PDF)
            attachments.append({"mime_type": mime, "data": file_bytes})

        # 5. Build prompt
        prompt = self._build_prompt(filename, mime, rubric, text_content)

        # 6. Call multimodal LLM
        system = (
            "You are an expert artifact reviewer. You produce structured, actionable "
            "feedback in JSON format. Always respond with valid JSON matching the "
            "requested schema. Be specific about locations, evidence, and fixes."
        )

        raw = self._llm.complete_multimodal(
            prompt=prompt,
            attachments=attachments,
            system=system,
            max_tokens=4096,
            thinking=request.thinking,
        )

        # 7. Parse LLM response into ReviewReport
        report = self._parse_response(raw, rubric, artifact_ref)
        now = self._clock.now()
        report.reviewed_at = now.iso()
        report.model = request.model or "gemini-2.0-flash"

        # 8. Store review output
        review_dir = self._store_review(
            report=report,
            artifact_path=artifact_path,
            rubric=rubric,
            prompt=prompt,
            model_name=report.model,
            now_iso=now.iso(),
        )

        self._log.info(
            f"Review complete: score={report.overall_score}, "
            f"pass={'YES' if report.passed else 'NO'}, "
            f"issues={len(report.issues)}"
        )

        return ReviewResponse(
            report=report,
            review_dir=review_dir,
            report_json=report.to_dict(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_rubric(self, rubric_path: str | None) -> dict[str, Any]:
        if rubric_path is None:
            return DEFAULT_RUBRIC
        path = os.path.abspath(rubric_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Rubric not found: {rubric_path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def _build_prompt(
        self,
        filename: str,
        mime: str,
        rubric: dict[str, Any],
        text_content: str | None,
    ) -> str:
        criteria_text = "\n".join(
            f"  - {c['name']} (weight: {c['weight']}): {c['description']}"
            for c in rubric.get("criteria", [])
        )
        pass_threshold = rubric.get("pass_threshold", 60)

        parts = [
            f"Review the following artifact: **{filename}** (type: {mime})",
            "",
            f"## Rubric: {rubric.get('name', 'general')}",
            f"{rubric.get('description', '')}",
            f"Pass threshold: {pass_threshold}/100",
            "",
            "### Criteria",
            criteria_text,
            "",
        ]

        if text_content:
            # Truncate very large text content
            max_chars = 30_000
            tc = text_content[:max_chars]
            if len(text_content) > max_chars:
                tc += "\n\n[... content truncated ...]"
            parts.append("### Artifact content (text)")
            parts.append("```")
            parts.append(tc)
            parts.append("```")
            parts.append("")

        parts.extend([
            "### Required JSON output schema",
            "Respond ONLY with valid JSON (no markdown fences, no extra text):",
            json.dumps({
                "overall_score": "number 0-100",
                "pass": "boolean",
                "summary": "string (2-4 sentence overview)",
                "issues": [
                    {
                        "severity": "critical|major|minor|suggestion",
                        "title": "short title",
                        "location": "where in the artifact",
                        "evidence": "what you observed",
                        "fix": "recommended fix",
                    }
                ],
                "next_steps": ["actionable next step 1", "..."],
            }, indent=2),
            "",
            "Rules:",
            f"- overall_score: 0-100. Set pass=true if score >= {pass_threshold}.",
            "- issues: sorted by severity (critical first). Include at least 1 issue or suggestion.",
            "- Be specific: reference exact locations, text, or visual elements.",
            "- next_steps: 2-5 concrete, actionable items.",
        ])

        return "\n".join(parts)

    def _parse_response(
        self,
        raw: str,
        rubric: dict[str, Any],
        artifact: ArtifactRef,
    ) -> ReviewReport:
        """Parse LLM JSON response into a ReviewReport, with fallback."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
            first_nl = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_nl + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    data = None
            else:
                data = None

        if data is None:
            # Fallback: create a report from raw text
            return ReviewReport(
                overall_score=0,
                passed=False,
                summary=f"Failed to parse structured response. Raw output: {raw[:500]}",
                issues=[
                    ReviewIssue(
                        severity=Severity.CRITICAL,
                        title="LLM response parse failure",
                        location="N/A",
                        evidence=raw[:200],
                        fix="Retry the review or adjust the prompt.",
                    )
                ],
                next_steps=["Retry the review"],
                artifact=artifact,
            )

        pass_threshold = rubric.get("pass_threshold", 60)
        score = int(data.get("overall_score", 0))

        issues = []
        for item in data.get("issues", []):
            try:
                issues.append(ReviewIssue.from_dict(item))
            except (KeyError, ValueError):
                continue

        # Sort issues by severity
        issues.sort(key=lambda i: i.severity)

        return ReviewReport(
            overall_score=score,
            passed=data.get("pass", score >= pass_threshold),
            summary=data.get("summary", ""),
            issues=issues,
            next_steps=data.get("next_steps", []),
            artifact=artifact,
        )

    def _store_review(
        self,
        report: ReviewReport,
        artifact_path: str,
        rubric: dict[str, Any],
        prompt: str,
        model_name: str,
        now_iso: str,
    ) -> str:
        """Persist the review to ./research/reviews/<timestamp>__<slug>/."""
        # Build slug from filename
        filename = os.path.basename(artifact_path)
        slug = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename).lower()
        ts = now_iso.replace(":", "-").replace("+", "p")[:19]
        review_name = f"{ts}__{slug}"

        base = self._store.base_path()
        review_dir = os.path.join(base, "reviews", review_name)
        input_dir = os.path.join(review_dir, "input")
        traces_dir = os.path.join(review_dir, "traces")

        for d in [review_dir, input_dir, traces_dir]:
            os.makedirs(d, exist_ok=True)

        # Copy artifact to input/
        shutil.copy2(artifact_path, os.path.join(input_dir, filename))

        # Save rubric
        with open(os.path.join(review_dir, "rubric.json"), "w", encoding="utf-8") as f:
            json.dump(rubric, f, indent=2)

        # Save report.json
        with open(os.path.join(review_dir, "report.json"), "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        # Save report.md
        md = self._report_to_markdown(report)
        with open(os.path.join(review_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write(md)

        # Save traces
        with open(os.path.join(traces_dir, "prompt.txt"), "w", encoding="utf-8") as f:
            from research_toolkit.infrastructure.config import redact_secrets
            f.write(redact_secrets(prompt))

        with open(os.path.join(traces_dir, "model_meta.json"), "w", encoding="utf-8") as f:
            json.dump({
                "model": model_name,
                "reviewed_at": now_iso,
                "artifact": os.path.basename(artifact_path),
                "artifact_mime": report.artifact.mime_type if report.artifact else "unknown",
            }, f, indent=2)

        return review_dir

    @staticmethod
    def _report_to_markdown(report: ReviewReport) -> str:
        """Render a ReviewReport as human-readable markdown."""
        lines = [
            "# Artifact Review Report",
            "",
            f"**Score:** {report.overall_score}/100  ",
            f"**Pass:** {'YES ✓' if report.passed else 'NO ✗'}  ",
        ]
        if report.artifact:
            lines.append(f"**Artifact:** {report.artifact.filename} ({report.artifact.mime_type})  ")
        if report.model:
            lines.append(f"**Model:** {report.model}  ")
        if report.reviewed_at:
            lines.append(f"**Reviewed:** {report.reviewed_at}  ")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(report.summary)
        lines.append("")

        if report.issues:
            lines.append("## Issues")
            lines.append("")
            for i, issue in enumerate(report.issues, 1):
                icon = {"critical": "🔴", "major": "🟠", "minor": "🟡", "suggestion": "💡"}.get(
                    issue.severity.value, "•"
                )
                lines.append(f"### {i}. {icon} [{issue.severity.value.upper()}] {issue.title}")
                lines.append("")
                lines.append(f"- **Location:** {issue.location}")
                lines.append(f"- **Evidence:** {issue.evidence}")
                lines.append(f"- **Fix:** {issue.fix}")
                lines.append("")

        if report.next_steps:
            lines.append("## Next Steps")
            lines.append("")
            for step in report.next_steps:
                lines.append(f"- {step}")
            lines.append("")

        return "\n".join(lines)
