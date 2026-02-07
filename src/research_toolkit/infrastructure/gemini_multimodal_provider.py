"""Infrastructure: Gemini multimodal provider – supports text + file attachments."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from research_toolkit.application.ports import MultimodalLLMProvider


class GeminiMultimodalProvider(MultimodalLLMProvider):
    """Multimodal LLM provider using Gemini's generateContent API.

    Accepts text prompts plus binary attachments (images, PDFs)
    as inline base64 data via the REST API.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: int = 120,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------
    def complete_multimodal(
        self,
        prompt: str,
        attachments: list[dict[str, Any]],
        *,
        system: str = "",
        max_tokens: int = 4096,
        thinking: str | None = None,
    ) -> str:
        url = f"{self.BASE_URL}/models/{self._model}:generateContent"

        # Build parts: text + inline file data
        parts: list[dict[str, Any]] = []

        # Add file attachments first (so the model "sees" them before the prompt)
        for att in attachments:
            mime_type = att["mime_type"]
            data_bytes: bytes = att["data"]
            b64 = base64.standard_b64encode(data_bytes).decode("ascii")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64,
                }
            })

        # Add text prompt
        parts.append({"text": prompt})

        contents: list[dict[str, Any]] = [{"role": "user", "parts": parts}]

        # System instruction
        system_instruction = None
        if system:
            system_instruction = {"parts": [{"text": system}]}

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2,
                "responseMimeType": "text/plain",
            },
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        # Thinking budget (Gemini 2.0 Flash Thinking feature)
        if thinking == "high":
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 8192}
        elif thinking == "low":
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 1024}

        try:
            resp = httpx.post(
                url,
                params={"key": self._api_key},
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            content_parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in content_parts)

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response else ""
            raise RuntimeError(
                f"Gemini multimodal API error ({exc.response.status_code}): {body}"
            ) from exc
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Gemini multimodal API timed out after {self._timeout}s. "
                "Try a smaller file or simpler rubric."
            )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @classmethod
    def is_available(cls, api_key: str, timeout: int = 5) -> bool:
        """Quick key validation check."""
        try:
            resp = httpx.get(
                f"{cls.BASE_URL}/models",
                params={"key": api_key},
                timeout=timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False
