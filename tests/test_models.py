import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from api.db import get_database_url
from api.models import Agent, Conversation, Message, Organization


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    engine = create_async_engine(get_database_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as db_session:
            yield db_session
        if transaction.is_active:
            await transaction.rollback()
    await engine.dispose()


async def create_org_with_agent(session: AsyncSession, name: str):
    org = Organization(name=name, slug=f"{name}-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    agent = Agent(
        organization_id=org.id,
        name="Sales Assistant",
        system_prompt="You are a helpful sales assistant.",
    )
    session.add(agent)
    await session.flush()
    return org, agent


@pytest.mark.anyio
async def test_save_conversation_with_messages(session):
    org, agent = await create_org_with_agent(session, "acme")

    conversation = Conversation(
        organization_id=org.id, agent_id=agent.id, channel="text"
    )
    session.add(conversation)
    await session.flush()

    session.add_all(
        [
            Message(
                organization_id=org.id,
                conversation_id=conversation.id,
                role="user",
                content="Pro plan ka price kya hai?",
            ),
            Message(
                organization_id=org.id,
                conversation_id=conversation.id,
                role="assistant",
                content="Pro plan 2999 rupaye per month hai.",
            ),
        ]
    )
    await session.flush()

    result = await session.execute(
        select(Message.role).where(Message.conversation_id == conversation.id)
    )
    assert sorted(result.scalars().all()) == ["assistant", "user"]


@pytest.mark.anyio
async def test_conversation_cannot_use_agent_from_another_company(session):
    _, agent_of_company_a = await create_org_with_agent(session, "company-a")
    company_b, _ = await create_org_with_agent(session, "company-b")

    session.add(
        Conversation(
            organization_id=company_b.id,
            agent_id=agent_of_company_a.id,
            channel="text",
        )
    )

    with pytest.raises(IntegrityError):
        await session.flush()