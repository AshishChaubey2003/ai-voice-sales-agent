from collections.abc import Awaitable, Callable

SaveMessage = Callable[[str, str, dict], Awaitable[None]]


class VoiceTurnRecorder:
    """Collects per-turn latency metrics and saves finished turns."""

    def __init__(self, save_message: SaveMessage, config: dict | None = None) -> None:
        self._save_message = save_message
        self._config = dict(config or {})
        self._stt_ms: int | None = None
        self._clear_assistant_metrics()

    def _clear_assistant_metrics(self) -> None:
        self._llm_ms: int | None = None
        self._tts_ms: int | None = None
        self._voice_to_voice_ms: int | None = None
        self._first_speech_ms: int | None = None
        self._rag_ms: int | None = None
        self._rag_sources: list[str] | None = None
        self._rag_rewritten_query: str | None = None

    def record_service_ttfb(self, processor_name: str, seconds: float | None) -> None:
        if not seconds or seconds <= 0:
            return
        ms = round(seconds * 1000)
        name = processor_name.upper()
        if "STT" in name:
            self._stt_ms = ms
        elif "LLM" in name and self._llm_ms is None:
            self._llm_ms = ms
        elif "TTS" in name and self._tts_ms is None:
            self._tts_ms = ms

    def record_voice_to_voice(self, seconds: float | None) -> None:
        if seconds and seconds > 0:
            self._voice_to_voice_ms = round(seconds * 1000)

    def record_first_speech(self, seconds: float | None) -> None:
        if seconds and seconds > 0:
            self._first_speech_ms = round(seconds * 1000)

    def record_retrieval(
        self, elapsed_ms: int, sources: list[str], rewritten_query: str | None
    ) -> None:
        self._rag_ms = elapsed_ms
        self._rag_sources = list(sources)
        self._rag_rewritten_query = rewritten_query

    async def user_turn_finished(self, text: str | None) -> None:
        metrics = {"stt_ttfb_ms": self._stt_ms}
        self._stt_ms = None
        text = (text or "").strip()
        if text:
            await self._save_message("user", text, self._build_latency(metrics))

    async def assistant_turn_finished(self, text: str | None, interrupted: bool) -> None:
        metrics = {
            "llm_ttfb_ms": self._llm_ms,
            "tts_ttfb_ms": self._tts_ms,
            "voice_to_voice_ms": self._voice_to_voice_ms,
            "first_speech_ms": self._first_speech_ms,
            "rag_ms": self._rag_ms,
            "rag_sources": self._rag_sources,
            "rag_rewritten_query": self._rag_rewritten_query,
        }
        self._clear_assistant_metrics()
        text = (text or "").strip()
        if text:
            await self._save_message(
                "assistant",
                text,
                self._build_latency(metrics, interrupted=bool(interrupted)),
            )

    def _build_latency(self, metrics: dict, **extra) -> dict:
        data = {key: value for key, value in metrics.items() if value is not None}
        data.update(extra)
        data.update(self._config)
        return data