import pytest

from voice.turn_recorder import VoiceTurnRecorder


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeStore:
    def __init__(self):
        self.saved = []

    async def save(self, role, content, latency):
        self.saved.append((role, content, latency))


@pytest.mark.anyio
async def test_user_turn_is_saved_with_stt_latency_and_config():
    store = FakeStore()
    recorder = VoiceTurnRecorder(store.save, config={"reasoning_effort": "low"})

    recorder.record_service_ttfb("GroqSTTService#0", 0.52)
    await recorder.user_turn_finished("What is my name?")

    assert store.saved == [
        ("user", "What is my name?", {"stt_ttfb_ms": 520, "reasoning_effort": "low"})
    ]


@pytest.mark.anyio
async def test_assistant_turn_keeps_first_llm_and_tts_values_then_resets():
    store = FakeStore()
    recorder = VoiceTurnRecorder(store.save)

    recorder.record_service_ttfb("GroqLLMService#0", 0.40)
    recorder.record_service_ttfb("GroqLLMService#0", 0.90)
    recorder.record_service_ttfb("GroqTTSService#0", 0.65)
    recorder.record_voice_to_voice(1.8)
    await recorder.assistant_turn_finished("Your name is Rahul.", interrupted=False)
    await recorder.assistant_turn_finished("Anything else?", interrupted=False)

    assert store.saved[0][2] == {
        "llm_ttfb_ms": 400,
        "tts_ttfb_ms": 650,
        "voice_to_voice_ms": 1800,
        "interrupted": False,
    }
    assert store.saved[1][2] == {"interrupted": False}


@pytest.mark.anyio
async def test_empty_turns_and_zero_metrics_are_ignored():
    store = FakeStore()
    recorder = VoiceTurnRecorder(store.save)

    recorder.record_service_ttfb("GroqSTTService#0", 0.0)
    await recorder.user_turn_finished("   ")
    await recorder.assistant_turn_finished(None, interrupted=True)

    assert store.saved == []


@pytest.mark.anyio
async def test_retrieval_details_are_saved_on_the_assistant_turn():
    store = FakeStore()
    recorder = VoiceTurnRecorder(store.save)

    recorder.record_retrieval(35, ["NimbusCRM Pricing > Pro plan"], None)
    await recorder.assistant_turn_finished("The Pro plan is $29.", interrupted=False)

    assert store.saved[0][2] == {
        "rag_ms": 35,
        "rag_sources": ["NimbusCRM Pricing > Pro plan"],
        "interrupted": False,
    }