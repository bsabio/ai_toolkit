"""Unit tests for the ReviewArtifact use case with mocked provider."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from research_toolkit.application.use_cases.review_artifact import (
    ReviewArtifact,
    ReviewRequest,
    ReviewResponse,
    detect_mime,
    DEFAULT_RUBRIC,
)
from research_toolkit.domain.review_entities import (
    ReviewReport,
    ReviewIssue,
    Severity,
    ArtifactRef,
)
from research_toolkit.infrastructure.filesystem_store import FilesystemStore
from research_toolkit.infrastructure.clock import WallClock
from research_toolkit.infrastructure.logger import ConsoleLogger

# conftest.py is auto-loaded by pytest but not directly importable;
# import via the tests package instead.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from conftest import MockMultimodalProvider, MOCK_REVIEW_JSON  # noqa: E402


# ---------------------------------------------------------------------------
# MIME detection tests
# ---------------------------------------------------------------------------
class TestMimeDetection:
    def test_png(self):
        assert detect_mime("screenshot.png") == "image/png"

    def test_jpg(self):
        assert detect_mime("photo.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert detect_mime("photo.jpeg") == "image/jpeg"

    def test_pdf(self):
        assert detect_mime("report.pdf") == "application/pdf"

    def test_markdown(self):
        assert detect_mime("README.md") == "text/markdown"

    def test_txt(self):
        assert detect_mime("notes.txt") == "text/plain"

    def test_json(self):
        assert detect_mime("data.json") == "application/json"

    def test_csv(self):
        assert detect_mime("data.csv") == "text/csv"

    def test_html(self):
        assert detect_mime("page.html") == "text/html"

    def test_unknown(self):
        result = detect_mime("file.xyz")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Domain entity tests
# ---------------------------------------------------------------------------
class TestReviewEntities:
    def test_severity_ordering(self):
        assert Severity.CRITICAL < Severity.MAJOR
        assert Severity.MAJOR < Severity.MINOR
        assert Severity.MINOR < Severity.SUGGESTION

    def test_review_issue_roundtrip(self):
        issue = ReviewIssue(
            severity=Severity.MAJOR,
            title="Test issue",
            location="Line 42",
            evidence="Found a problem",
            fix="Fix the problem",
        )
        d = issue.to_dict()
        restored = ReviewIssue.from_dict(d)
        assert restored.severity == Severity.MAJOR
        assert restored.title == "Test issue"

    def test_review_report_roundtrip(self):
        report = ReviewReport(
            overall_score=85,
            passed=True,
            summary="Good report",
            issues=[
                ReviewIssue(Severity.MINOR, "Small thing", "Page 1", "Noticed it", "Fix it")
            ],
            next_steps=["Do this", "Do that"],
            artifact=ArtifactRef("test.png", "test.png", "image/png", 1234),
            model="gemini-2.0-flash",
            reviewed_at="2026-01-01T00:00:00+00:00",
        )
        d = report.to_dict()
        assert d["overall_score"] == 85
        assert d["pass"] is True
        assert len(d["issues"]) == 1
        assert d["issues"][0]["severity"] == "minor"

        restored = ReviewReport.from_dict(d)
        assert restored.overall_score == 85
        assert restored.passed is True

    def test_artifact_ref_roundtrip(self):
        ref = ArtifactRef("/path/to/file.pdf", "file.pdf", "application/pdf", 5000)
        d = ref.to_dict()
        restored = ArtifactRef.from_dict(d)
        assert restored.filename == "file.pdf"
        assert restored.mime_type == "application/pdf"


# ---------------------------------------------------------------------------
# Use case tests (with mock provider)
# ---------------------------------------------------------------------------
class TestReviewArtifactUseCase:
    def _make_uc(self, tmpdir, mock_response=MOCK_REVIEW_JSON):
        store = FilesystemStore(str(tmpdir))
        store.ensure_dirs()
        clock = WallClock()
        logger = ConsoleLogger()
        mock_llm = MockMultimodalProvider(response=mock_response)
        uc = ReviewArtifact(llm=mock_llm, store=store, clock=clock, logger=logger)
        return uc, mock_llm

    def test_review_png(self, sample_ui_png, tmp_path):
        uc, mock_llm = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png)
        resp = uc.execute(req)

        assert isinstance(resp, ReviewResponse)
        assert resp.report.overall_score == 72
        assert resp.report.passed is True
        assert len(resp.report.issues) == 3
        assert resp.report.issues[0].severity == Severity.MAJOR

        # Check mock was called with attachment (binary)
        assert mock_llm.calls[0]["num_attachments"] == 1

    def test_review_markdown(self, sample_report_md, tmp_path):
        uc, mock_llm = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_report_md)
        resp = uc.execute(req)

        assert isinstance(resp, ReviewResponse)
        # Text files: no binary attachments, text included in prompt
        assert mock_llm.calls[0]["num_attachments"] == 0

    def test_review_pdf(self, sample_report_pdf, tmp_path):
        uc, mock_llm = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_report_pdf)
        resp = uc.execute(req)

        assert isinstance(resp, ReviewResponse)
        # PDF goes as binary attachment
        assert mock_llm.calls[0]["num_attachments"] == 1

    def test_review_with_rubric(self, sample_ui_png, rubric_ui, tmp_path):
        uc, mock_llm = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png, rubric_path=rubric_ui)
        resp = uc.execute(req)

        # Rubric should appear in prompt
        prompt = mock_llm.calls[0]["prompt"]
        assert "Visual Hierarchy" in prompt
        assert "Accessibility" in prompt

    def test_review_stores_output(self, sample_ui_png, tmp_path):
        uc, _ = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png)
        resp = uc.execute(req)

        review_dir = resp.review_dir
        assert os.path.isdir(review_dir)
        assert os.path.isfile(os.path.join(review_dir, "report.json"))
        assert os.path.isfile(os.path.join(review_dir, "report.md"))
        assert os.path.isfile(os.path.join(review_dir, "rubric.json"))
        assert os.path.isdir(os.path.join(review_dir, "input"))
        assert os.path.isdir(os.path.join(review_dir, "traces"))
        assert os.path.isfile(os.path.join(review_dir, "traces", "prompt.txt"))
        assert os.path.isfile(os.path.join(review_dir, "traces", "model_meta.json"))

        # Verify report.json is valid
        with open(os.path.join(review_dir, "report.json")) as f:
            data = json.load(f)
        assert data["overall_score"] == 72
        assert data["pass"] is True

    def test_review_nonexistent_file(self, tmp_path):
        uc, _ = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path="/nonexistent/file.png")
        with pytest.raises(FileNotFoundError):
            uc.execute(req)

    def test_review_nonexistent_rubric(self, sample_ui_png, tmp_path):
        uc, _ = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png, rubric_path="/nonexistent/rubric.json")
        with pytest.raises(FileNotFoundError):
            uc.execute(req)

    def test_review_malformed_json_response(self, sample_ui_png, tmp_path):
        """When LLM returns invalid JSON, the use case should fallback gracefully."""
        uc, _ = self._make_uc(tmp_path, mock_response="This is not JSON at all.")
        req = ReviewRequest(artifact_path=sample_ui_png)
        resp = uc.execute(req)

        assert resp.report.overall_score == 0
        assert resp.report.passed is False
        assert "parse failure" in resp.report.issues[0].title.lower()

    def test_report_json_has_correct_schema(self, sample_ui_png, tmp_path):
        """Verify the JSON output matches required schema fields."""
        uc, _ = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png)
        resp = uc.execute(req)

        data = resp.report_json
        assert "overall_score" in data
        assert "pass" in data
        assert "summary" in data
        assert "issues" in data
        assert "next_steps" in data
        assert isinstance(data["overall_score"], int)
        assert isinstance(data["pass"], bool)
        assert isinstance(data["issues"], list)
        assert isinstance(data["next_steps"], list)

        for issue in data["issues"]:
            assert "severity" in issue
            assert "title" in issue
            assert "location" in issue
            assert "evidence" in issue
            assert "fix" in issue

    def test_thinking_parameter_passed(self, sample_ui_png, tmp_path):
        uc, mock_llm = self._make_uc(tmp_path)
        req = ReviewRequest(artifact_path=sample_ui_png, thinking="high")
        uc.execute(req)
        assert mock_llm.calls[0]["thinking"] == "high"
