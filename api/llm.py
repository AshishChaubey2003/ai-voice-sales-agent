import time
from dataclasses import dataclass
from typing import Protocol

from groq import AsyncGroq


@dataclass
class LLMReply:
    text: str
    latency_ms: int


class LLMError(Exception):
    """LLM provider se jawab nahi mila."""


class LLMClient(Protocol):
    async def generate(
        self, system_prompt: str, history: list[dict[str, str]]
    ) -> LLMReply: ...


class GroqLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        reasoning_effort: str | None = None,
    ) -> None:
        self._client = AsyncGroq(
            api_key=api_key, timeout=timeout_seconds, max_retries=1
        )
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort

    async def generate(
        self, system_prompt: str, history: list[dict[str, str]]
    ) -> LLMReply:
        messages = [{"role": "system", "content": system_prompt}, *history]
        extra_body = (
            {"reasoning_effort": self._reasoning_effort}
            if self._reasoning_effort
            else None
        )

        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=self._max_output_tokens,
                temperature=0.3,
                extra_body=extra_body,
            )
        except Exception as exc:
            raise LLMError(type(exc).__name__) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        if not text:
            raise LLMError(f"empty_response finish_reason={choice.finish_reason}")
        return LLMReply(text=text, latency_ms=latency_ms)

    async def close(self) -> None:
        await self._client.close()