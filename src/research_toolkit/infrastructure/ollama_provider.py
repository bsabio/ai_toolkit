"""Infrastructure: Ollama LLM provider – local inference via Ollama's OpenAI-compatible API."""

from __future__ import annotations

import httpx

from research_toolkit.application.ports import LLMProvider


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama instance.

    Ollama exposes an OpenAI-compatible chat endpoint at
    ``http://<host>:<port>/v1/chat/completions``.  This provider talks to
    that endpoint directly via httpx so the heavy ``openai`` SDK is not
    required for purely-local use.
    """

    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        model: str = "llama3.1",
        host: str | None = None,
        timeout: int = 300,
    ) -> None:
        self._model = model
        self._host = (host or self.DEFAULT_HOST).rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2048) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.3,
            },
        }

        try:
            resp = httpx.post(
                f"{self._host}/api/chat",
                json=payload,
                timeout=self._timeout,
            )
            # If model is too large, try to fall back to a smaller one
            if resp.status_code == 500:
                body = resp.text
                if "requires more system memory" in body or "out of memory" in body.lower():
                    fallback = self._find_smaller_model()
                    if fallback and fallback != self._model:
                        payload["model"] = fallback
                        resp = httpx.post(
                            f"{self._host}/api/chat",
                            json=payload,
                            timeout=self._timeout,
                        )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except httpx.HTTPStatusError:
            raise
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Ollama timed out after {self._timeout}s. "
                "The model may be loading for the first time, or the prompt is very long. "
                "Try again or use a smaller model."
            )

    def _find_smaller_model(self) -> str | None:
        """Return the name of the smallest available model as a fallback."""
        models = self.list_models(self._host)
        if not models:
            return None
        # Sort by size string (crude but effective)
        models.sort(key=lambda m: float(m["size"].replace(" GB", "") or "999"))
        return models[0]["name"]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @classmethod
    def list_models(cls, host: str | None = None) -> list[dict[str, str]]:
        """Return a list of models available on the Ollama instance."""
        base = (host or cls.DEFAULT_HOST).rstrip("/")
        try:
            resp = httpx.get(f"{base}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m["name"],
                    "size": f"{m.get('size', 0) / 1e9:.1f} GB",
                    "family": m.get("details", {}).get("family", ""),
                    "params": m.get("details", {}).get("parameter_size", ""),
                    "quant": m.get("details", {}).get("quantization_level", ""),
                })
            return models
        except Exception:
            return []

    @classmethod
    def is_available(cls, host: str | None = None) -> bool:
        """Check whether the Ollama daemon is reachable."""
        base = (host or cls.DEFAULT_HOST).rstrip("/")
        try:
            resp = httpx.get(f"{base}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False
