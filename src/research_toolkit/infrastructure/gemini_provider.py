"""Infrastructure: Google Gemini LLM provider via REST API."""

from __future__ import annotations

import httpx

from research_toolkit.application.ports import LLMProvider


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google's Gemini API.

    Uses the ``v1beta/models/{model}:generateContent`` REST endpoint
    directly via httpx – no heavy SDK required.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: int = 60,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2048) -> str:
        url = f"{self.BASE_URL}/models/{self._model}:generateContent"

        contents: list[dict] = []

        # System instruction goes in a separate top-level field
        system_instruction = None
        if system:
            system_instruction = {"parts": [{"text": system}]}

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        try:
            resp = httpx.post(
                url,
                params={"key": self._api_key},
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response else ""
            raise RuntimeError(
                f"Gemini API error ({exc.response.status_code}): {body}"
            ) from exc
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Gemini API timed out after {self._timeout}s. "
                "Try again or use a smaller prompt."
            )

    # ------------------------------------------------------------------
    # Utility class methods
    # ------------------------------------------------------------------
    @classmethod
    def is_available(cls, api_key: str, timeout: int = 5) -> bool:
        """Quick check: can we reach Gemini and is the key valid?"""
        try:
            resp = httpx.get(
                f"{cls.BASE_URL}/models",
                params={"key": api_key},
                timeout=timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def list_models(cls, api_key: str, timeout: int = 10) -> list[dict[str, str]]:
        """Return available Gemini models."""
        try:
            resp = httpx.get(
                f"{cls.BASE_URL}/models",
                params={"key": api_key},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                # Only include generative models
                if "generateContent" in str(m.get("supportedGenerationMethods", [])):
                    models.append({
                        "name": name,
                        "display_name": m.get("displayName", name),
                        "input_token_limit": str(m.get("inputTokenLimit", "?")),
                        "output_token_limit": str(m.get("outputTokenLimit", "?")),
                    })
            return models
        except Exception:
            return []
