import asyncio

from sqlalchemy import select

from api.db import build_engine, build_session_factory
from api.models import Agent, Organization

DEMO_SLUG = "nimbus-crm-demo"
AGENT_NAME = "Nimbus Sales Assistant"

SYSTEM_PROMPT = """You are the AI sales assistant for NimbusCRM, a fictional CRM software company used for demos.

Rules:
- Keep answers short: 1 to 3 sentences, friendly and professional.
- Answer questions about NimbusCRM only from the knowledge base provided with each message. If the answer is not there, say you don't have that information and offer to pass the question to the sales team.
- You cannot book meetings, schedule calls, or send anything yet. If the visitor asks for a call or demo, say you will pass their request to the sales team. Never say that anything has been booked, arranged, or scheduled, and never promise when the sales team will reach out.
- Ask at most one question at a time to understand the visitor's needs (team size, main problem, timeline). Do not repeat a question the visitor has already answered.
- Never ask for passwords, card numbers or other sensitive data.
- Reply in the language the visitor uses (English or Hinglish)."""

async def main() -> None:
    engine = build_engine()
    session_factory = build_session_factory(engine)

    async with session_factory() as session:
        org = await session.scalar(
            select(Organization).where(Organization.slug == DEMO_SLUG)
        )
        if org is None:
            org = Organization(name="NimbusCRM (Demo)", slug=DEMO_SLUG)
            session.add(org)
            await session.flush()

        agent = await session.scalar(
            select(Agent).where(
                Agent.organization_id == org.id, Agent.name == AGENT_NAME
            )
        )
        if agent is None:
            agent = Agent(
                organization_id=org.id, name=AGENT_NAME, system_prompt=SYSTEM_PROMPT
            )
            session.add(agent)
        else:
            agent.system_prompt = SYSTEM_PROMPT

        await session.commit()
        print(f"Demo agent ready. agent_id = {agent.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())