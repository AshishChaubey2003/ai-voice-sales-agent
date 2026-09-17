import asyncio

from api.config import get_settings
from api.llm import GroqLLM


async def main() -> None:
    settings = get_settings()
    llm = GroqLLM(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=20,
    )
    try:
        reply = await llm.generate(
            "Reply in one short sentence.",
            [{"role": "user", "content": "Say hello"}],
        )
        print("OK:", reply.text, f"({reply.latency_ms} ms)")
    except Exception as exc:
        cause = exc.__cause__
        print("FAILED:", type(cause).__name__)
        print("status:", getattr(cause, "status_code", None))
        print("message:", str(cause)[:300])
    finally:
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())