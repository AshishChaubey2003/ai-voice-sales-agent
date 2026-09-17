import argparse
import asyncio

from sqlalchemy import select

from api.config import get_settings
from api.db import build_engine, build_session_factory
from api.knowledge import search_knowledge
from api.models import Organization


async def run(question: str, org_slug: str) -> None:
    settings = get_settings()
    engine = build_engine()
    try:
        async with build_session_factory(engine)() as session:
            org = await session.scalar(
                select(Organization).where(Organization.slug == org_slug)
            )
            if org is None:
                raise SystemExit(f"Organization '{org_slug}' not found")
            result = await search_knowledge(
                session,
                org.id,
                question,
                top_k=settings.rag_top_k,
                max_distance=settings.rag_max_distance,
            )
    finally:
        await engine.dispose()

    print(f"\nQuestion: {question}  ({result.elapsed_ms} ms)\n")
    if not result.chunks:
        print(f"No relevant chunks (nothing within distance {settings.rag_max_distance}).")
    for position, chunk in enumerate(result.chunks, start=1):
        distance = f"{chunk.vector_distance:.3f}" if chunk.vector_distance is not None else "-"
        rank = f"{chunk.keyword_rank:.3f}" if chunk.keyword_rank is not None else "-"
        print(f"[{position}] {chunk.heading}  (vector distance {distance}, keyword rank {rank})")
        print(f"    {chunk.content[:150]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the knowledge base.")
    parser.add_argument("question")
    parser.add_argument("--org", default="nimbus-crm-demo")
    args = parser.parse_args()
    asyncio.run(run(args.question, args.org))


if __name__ == "__main__":
    main()