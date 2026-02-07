"""Configuration loader – reads .env and environment variables with secret redaction."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv


# Patterns that should NEVER be printed/logged
_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_-]{20,})"),
    re.compile(r"(AIzaSy[A-Za-z0-9_-]{20,})"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)\S+"),
    re.compile(r"(BRAVE_API_KEY\s*=\s*)\S+"),
    re.compile(r"(GOOGLE_API_KEY\s*=\s*)\S+"),
    re.compile(r"(GEMINI_API_KEY\s*=\s*)\S+"),
    re.compile(r"(SERPAPI_KEY\s*=\s*)\S+"),
    re.compile(r"(key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_-]{16,}"),
]


def redact_secrets(text: str) -> str:
    """Mask anything that looks like a secret in *text*."""
    result = text
    for pat in _SECRET_PATTERNS:
        result = pat.sub(lambda m: m.group(0)[:6] + "***REDACTED***", result)
    return result


def load_config(env_path: str | None = None) -> dict[str, str | None]:
    """Load configuration from .env file and environment variables.

    Returns a dict of the config keys this toolkit cares about.
    Values are never logged or printed.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        # Walk up to find .env
        cwd = Path.cwd()
        for d in [cwd, *cwd.parents]:
            candidate = d / ".env"
            if candidate.exists():
                load_dotenv(candidate)
                break

    return {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "OPENAI_MODEL": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY"),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
        "GOOGLE_CX": os.environ.get("GOOGLE_CX"),
        "SERPAPI_KEY": os.environ.get("SERPAPI_KEY"),
        # Gemini
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
        "GEMINI_MODEL": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        # Ollama (local LLM)
        "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
        # Provider preference: "ollama", "openai", "gemini", or "auto" (default)
        "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "auto"),
    }
