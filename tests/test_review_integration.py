"""Integration tests for the review CLI command (fixture replay mode)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pytest

from research_toolkit.adapters.cli import run_cli


class TestReviewCLIIntegration:
    """Test the CLI review command with mocked provider (no live API calls)."""

    def test_review_help(self):
        """tool help review should show usage information."""
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            run_cli(["help", "review"])
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        assert "review" in output.lower()
        assert "--rubric" in output

    def test_review_in_help_list(self):
        """tool help should list the review command."""
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            run_cli(["help"])
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        assert "review" in output

    def test_review_in_spec(self):
        """tool spec should include the review command."""
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            run_cli(["spec"])
        finally:
            sys.stdout = old_stdout
        spec = json.loads(captured.getvalue())
        assert "review" in spec["commands"]
        review_cmd = spec["commands"]["review"]
        assert "artifact" in review_cmd["description"].lower() or "review" in review_cmd["description"].lower()
