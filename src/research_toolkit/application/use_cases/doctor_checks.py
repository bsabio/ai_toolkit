"""Use-case: DoctorChecks – validate environment, storage, connectivity."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from research_toolkit.application.ports import Indexer, LLMProvider, Logger, SearchProvider, Store


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


@dataclass
class DoctorResponse:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


class DoctorChecks:
    """Run diagnostic checks on the toolkit environment."""

    def __init__(
        self,
        store: Store,
        indexer: Indexer,
        search_provider: SearchProvider | None,
        llm_provider: LLMProvider | None,
        logger: Logger,
    ) -> None:
        self._store = store
        self._indexer = indexer
        self._search = search_provider
        self._llm = llm_provider
        self._log = logger

    def execute(self) -> DoctorResponse:
        checks: list[CheckResult] = []

        # 1. Environment variables
        checks.append(self._check_env_vars())

        # 2. Storage permissions
        checks.append(self._check_storage())

        # 3. Ollama local LLM
        checks.append(self._check_ollama())

        # 4. Gemini API key
        checks.append(self._check_gemini())

        # 5. Search provider
        checks.append(self._check_search_provider())

        # 6. LLM provider (resolved)
        checks.append(self._check_llm_provider())

        # 7. Index health
        checks.append(self._check_index())

        return DoctorResponse(checks=checks)

    def _check_env_vars(self) -> CheckResult:
        """Check that required env vars are set (without revealing values)."""
        issues: list[str] = []
        info: list[str] = []

        # Check for at least one search provider key
        search_keys = ["BRAVE_API_KEY", "GOOGLE_API_KEY", "SERPAPI_KEY"]
        has_search = any(os.environ.get(k) for k in search_keys)
        if not has_search:
            issues.append("No search API key (need one of: BRAVE_API_KEY, GOOGLE_API_KEY, SERPAPI_KEY)")

        # OpenAI is optional when Ollama is available
        if os.environ.get("OPENAI_API_KEY"):
            info.append("OPENAI_API_KEY set")
        else:
            info.append("OPENAI_API_KEY not set (OK if using Ollama)")

        # Gemini
        if os.environ.get("GEMINI_API_KEY"):
            info.append("GEMINI_API_KEY set")
        else:
            info.append("GEMINI_API_KEY not set (needed for review command)")

        # Ollama config
        provider = os.environ.get("LLM_PROVIDER", "auto")
        info.append(f"LLM_PROVIDER={provider}")

        msg = "; ".join(info)
        if issues:
            return CheckResult(name="env_vars", passed=False, message="; ".join(issues) + " | " + msg)
        return CheckResult(name="env_vars", passed=True, message=msg)

    def _check_storage(self) -> CheckResult:
        """Check storage directory is writable."""
        try:
            self._store.ensure_dirs()
            base = self._store.base_path()
            if os.access(base, os.W_OK):
                return CheckResult(name="storage", passed=True, message=f"Storage writable at {base}")
            return CheckResult(name="storage", passed=False, message=f"Storage not writable at {base}")
        except Exception as e:
            return CheckResult(name="storage", passed=False, message=f"Storage error: {e}")

    def _check_search_provider(self) -> CheckResult:
        """Check search provider connectivity."""
        if self._search is None:
            return CheckResult(
                name="search_provider",
                passed=False,
                message="No search provider configured (set a search API key)",
            )
        return CheckResult(
            name="search_provider",
            passed=True,
            message="Search provider configured",
        )

    def _check_llm_provider(self) -> CheckResult:
        """Check LLM provider availability."""
        if self._llm is None:
            return CheckResult(
                name="llm_provider",
                passed=False,
                message="No LLM provider available. Start Ollama or set OPENAI_API_KEY.",
            )
        return CheckResult(
            name="llm_provider",
            passed=True,
            message="LLM provider ready",
        )

    def _check_ollama(self) -> CheckResult:
        """Check Ollama daemon reachability and list models."""
        try:
            import httpx
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            resp = httpx.get(f"{host}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return CheckResult(
                    name="ollama",
                    passed=True,
                    message=f"Ollama running at {host}; models: {', '.join(models) or 'none'}",
                )
            return CheckResult(name="ollama", passed=False, message=f"Ollama returned status {resp.status_code}")
        except Exception:
            return CheckResult(
                name="ollama",
                passed=False,
                message="Ollama not reachable (is 'ollama serve' running?)",
            )

    def _check_gemini(self) -> CheckResult:
        """Check Gemini API key is set (needed for review command)."""
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return CheckResult(
                name="gemini",
                passed=False,
                message="GEMINI_API_KEY not set. Required for 'tool review'.",
            )
        return CheckResult(
            name="gemini",
            passed=True,
            message="GEMINI_API_KEY set (needed for review command)",
        )

    def _check_index(self) -> CheckResult:
        """Check index/registry health."""
        try:
            healthy = self._indexer.healthy()
            if healthy:
                return CheckResult(name="index", passed=True, message="Index is healthy")
            return CheckResult(name="index", passed=False, message="Index reports unhealthy state")
        except Exception as e:
            return CheckResult(name="index", passed=False, message=f"Index error: {e}")
