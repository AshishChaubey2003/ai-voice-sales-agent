import asyncio
from collections import defaultdict

from sqlalchemy import select

from api.db import build_engine, build_session_factory
from api.models import Conversation, Message
from voice.stats import percentile

ROLE_METRICS = {
    "user": ["stt_ttfb_ms"],
    "assistant": ["llm_ttfb_ms", "tts_ttfb_ms", "voice_to_voice_ms", "first_speech_ms"],
}
REPORT_ORDER = [
    "stt_ttfb_ms",
    "llm_ttfb_ms",
    "first_llm_ttfb_ms",
    "tts_ttfb_ms",
    "voice_to_voice_ms",
    "first_speech_ms",
]
MIN_SAMPLES_FOR_P95 = 20


async def load_rows():
    engine = build_engine()
    try:
        async with build_session_factory(engine)() as session:
            result = await session.execute(
                select(Message.conversation_id, Message.role, Message.latency_ms)
                .join(
                    Conversation,
                    (Conversation.id == Message.conversation_id)
                    & (Conversation.organization_id == Message.organization_id),
                )
                .where(Conversation.channel == "voice", Message.latency_ms.is_not(None))
                .order_by(Message.conversation_id, Message.created_at)
            )
            return result.all()
    finally:
        await engine.dispose()


def build_label(latency: dict) -> str:
    reasoning = latency.get("reasoning_effort", "unknown")
    tts = latency.get("tts_provider", "groq")
    return f"reasoning={reasoning} | tts={tts}"


def group_metrics(rows):
    groups = defaultdict(lambda: defaultdict(list))
    conversations_with_llm = set()

    for conversation_id, role, latency in rows:
        label = build_label(latency)

        for key in ROLE_METRICS.get(role, []):
            value = latency.get(key)
            if isinstance(value, (int, float)):
                groups[label][key].append(value)

        llm_ms = latency.get("llm_ttfb_ms")
        if role == "assistant" and isinstance(llm_ms, (int, float)):
            if conversation_id not in conversations_with_llm:
                conversations_with_llm.add(conversation_id)
                groups[label]["first_llm_ttfb_ms"].append(llm_ms)

    return groups


def print_report(groups) -> None:
    if not groups:
        print("No voice latency data yet. Talk to the bot first.")
        return

    for label in sorted(groups):
        print(f"\n=== {label} ===")
        print(f"{'metric':<22}{'n':>5}{'p50 ms':>10}{'p95 ms':>10}")
        for key in REPORT_ORDER:
            values = groups[label].get(key, [])
            if not values:
                continue
            note = "  (few samples, p95 unreliable)" if len(values) < MIN_SAMPLES_FOR_P95 else ""
            print(
                f"{key:<22}{len(values):>5}"
                f"{percentile(values, 50):>10}{percentile(values, 95):>10}{note}"
            )


async def main() -> None:
    print_report(group_metrics(await load_rows()))


if __name__ == "__main__":
    asyncio.run(main())