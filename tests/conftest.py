"""Shared test fixtures and conftest for Research Toolkit tests."""

from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to the test fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sample_ui_png(fixtures_dir):
    """Return path to sample UI screenshot PNG."""
    return os.path.join(fixtures_dir, "sample-ui.png")


@pytest.fixture
def sample_chart_png(fixtures_dir):
    """Return path to sample chart PNG."""
    return os.path.join(fixtures_dir, "sample-chart.png")


@pytest.fixture
def sample_report_pdf(fixtures_dir):
    """Return path to sample report PDF."""
    return os.path.join(fixtures_dir, "sample-report.pdf")


@pytest.fixture
def sample_report_md(fixtures_dir):
    """Return path to sample markdown report."""
    return os.path.join(fixtures_dir, "sample-report.md")


@pytest.fixture
def rubric_ui():
    """Return path to UI rubric."""
    return os.path.join(os.path.dirname(__file__), "..", "rubrics", "ui.json")


@pytest.fixture
def rubric_docs():
    """Return path to docs rubric."""
    return os.path.join(os.path.dirname(__file__), "..", "rubrics", "docs.json")


# ---------------------------------------------------------------------------
# Mock LLM response (fixture replay mode)
# ---------------------------------------------------------------------------
MOCK_REVIEW_JSON = json.dumps({
    "overall_score": 72,
    "pass": True,
    "summary": "The artifact demonstrates adequate quality with some areas for improvement.",
    "issues": [
        {
            "severity": "major",
            "title": "Missing alt text for images",
            "location": "Header section",
            "evidence": "The header image does not include descriptive alt text.",
            "fix": "Add descriptive alt text: alt='Application dashboard header'",
        },
        {
            "severity": "minor",
            "title": "Low contrast on secondary text",
            "location": "Sidebar navigation",
            "evidence": "Gray text (#999) on white background (#fff) has contrast ratio 2.8:1.",
            "fix": "Darken text to #666 for WCAG AA compliance (4.5:1 ratio).",
        },
        {
            "severity": "suggestion",
            "title": "Consider adding loading states",
            "location": "Content area",
            "evidence": "No skeleton screens or spinners visible for async content.",
            "fix": "Add skeleton placeholders for data that loads asynchronously.",
        },
    ],
    "next_steps": [
        "Fix alt text on all images for accessibility compliance",
        "Update color palette for WCAG AA contrast ratios",
        "Add loading state wireframes to the design system",
    ],
})


class MockMultimodalProvider:
    """Mock multimodal LLM provider for testing (fixture replay mode)."""

    def __init__(self, response: str = MOCK_REVIEW_JSON):
        self._response = response
        self.calls: list[dict] = []

    def complete_multimodal(
        self,
        prompt: str,
        attachments: list,
        *,
        system: str = "",
        max_tokens: int = 4096,
        thinking: str | None = None,
    ) -> str:
        self.calls.append({
            "prompt": prompt,
            "num_attachments": len(attachments),
            "system": system,
            "max_tokens": max_tokens,
            "thinking": thinking,
        })
        return self._response
