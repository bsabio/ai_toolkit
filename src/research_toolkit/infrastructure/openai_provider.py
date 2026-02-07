"""Infrastructure: OpenAI-based LLM provider."""

from __future__ import annotations

from research_toolkit.application.ports import LLMProvider


class OpenAIProvider(LLMProvider):
    """LLM provider backed by the OpenAI API (or compatible endpoint)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 2048) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
