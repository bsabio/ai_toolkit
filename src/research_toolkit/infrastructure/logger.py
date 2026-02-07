"""Infrastructure: Logger with secret redaction."""

from __future__ import annotations

import sys
from typing import Any

from research_toolkit.application.ports import Logger as LoggerPort
from research_toolkit.infrastructure.config import redact_secrets


class ConsoleLogger(LoggerPort):
    """Simple stderr logger with automatic secret redaction."""

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose

    def _emit(self, level: str, msg: str, **kw: Any) -> None:
        safe = redact_secrets(msg)
        extras = " ".join(f"{k}={redact_secrets(str(v))}" for k, v in kw.items())
        line = f"[{level}] {safe}"
        if extras:
            line += f" ({extras})"
        print(line, file=sys.stderr)

    def info(self, msg: str, **kw: Any) -> None:
        self._emit("INFO", msg, **kw)

    def warn(self, msg: str, **kw: Any) -> None:
        self._emit("WARN", msg, **kw)

    def error(self, msg: str, **kw: Any) -> None:
        self._emit("ERROR", msg, **kw)

    def debug(self, msg: str, **kw: Any) -> None:
        if self._verbose:
            self._emit("DEBUG", msg, **kw)
