import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from api.db import build_engine, build_session_factory
from api.deps import get_knowledge_search, get_llm
from api.knowledge import RetrievedChunk, SearchResult
from api.llm import LLMError, LLMReply
from api.main import app
from api.models import Agent, Message, Organization


class FakeLLM:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []
        self.prompts = []

    async def generate(self, system_prompt, history):
        self.prompts.append(system_prompt)
        self.calls.append(history)
        if self.fail:
            raise LLMError("fake_failure")
        return LLMReply(text="Hello! How can I help you today?", latency_ms=42)


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def generate(self, system_prompt, history):
        self.prompts.append(system_prompt)
        return LLMReply(text=self.replies.pop(0), latency_ms=10)


def fake_search(chunks=None):
    async def search(session, organization_id, query, top_k=4, max_distance=None):
        return SearchResult(chunks=list(chunks or []), elapsed_ms=1)

    return search


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def setup():
    engine = build_engine()
    session_factory = build_session_factory(engine)
    app.state.session_factory = session_factory
    app.dependency_overrides[get_knowledge_search] = lambda: fake_search()

    async with session_factory() as session:
        org = Organization(name="Test Co", slug=f"test-{uuid.uuid4().hex[:8]}")
        session.add(org)
        await session.flush()
        agent = Agent(organization_id=org.id, name="Test Agent", system_prompt="Be brief.")
        session.add(agent)
        await session.commit()
        org_id, agent_id = org.id, agent.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_factory, agent_id

    async with session_factory() as session:
        await session.execute(delete(Organization).where(Organization.id == org_id))
        await session.commit()
    app.dependency_overrides.clear()
    await engine.dispose()


async def start_conversation(client, agent_id):
    response = await client.post("/v1/conversations", json={"agent_id": str(agent_id)})
    assert response.status_code == 201
    return response.json()["conversation_id"]


@pytest.mark.anyio
async def test_chat_saves_user_and_assistant_messages(setup):
    client, session_factory, agent_id = setup
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake

    conversation_id = await start_conversation(client, agent_id)
    response = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "Hi, what do you sell?"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Hello! How can I help you today?"
    assert fake.calls[0][-1] == {"role": "user", "content": "Hi, what do you sell?"}

    async with session_factory() as session:
        roles = (
            await session.scalars(
                select(Message.role).where(
                    Message.conversation_id == uuid.UUID(conversation_id)
                )
            )
        ).all()
    assert sorted(roles) == ["assistant", "user"]


@pytest.mark.anyio
async def test_reply_prompt_is_grounded_in_retrieved_knowledge(setup):
    client, _, agent_id = setup
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    pro_plan = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        title="NimbusCRM Pricing",
        heading="NimbusCRM Pricing > Pro plan",
        content="$29 per user per month.",
    )
    app.dependency_overrides[get_knowledge_search] = lambda: fake_search([pro_plan])

    conversation_id = await start_conversation(client, agent_id)
    response = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "How much is the Pro plan?"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == ["NimbusCRM Pricing > Pro plan"]
    assert "$29 per user per month." in fake.prompts[0]


@pytest.mark.anyio
async def test_follow_up_question_is_rewritten_when_first_search_finds_nothing(setup):
    client, _, agent_id = setup
    business_plan = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        title="NimbusCRM Pricing",
        heading="NimbusCRM Pricing > Business plan",
        content="$49 per user per month.",
    )
    searched_queries = []

    async def search(session, organization_id, query, top_k=4, max_distance=None):
        searched_queries.append(query)
        chunks = [business_plan] if query == "Business plan price" else []
        return SearchResult(chunks=chunks, elapsed_ms=1)

    llm = ScriptedLLM(["The Pro plan is $29.", "Business plan price", "The Business plan is $49."])
    app.dependency_overrides[get_knowledge_search] = lambda: search
    app.dependency_overrides[get_llm] = lambda: llm

    conversation_id = await start_conversation(client, agent_id)
    await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "How much is the Pro plan?"},
    )
    response = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "And what about the Business plan?"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == ["NimbusCRM Pricing > Business plan"]
    assert searched_queries[-1] == "Business plan price"
    assert "$49 per user per month." in llm.prompts[-1]


@pytest.mark.anyio
async def test_llm_failure_returns_503_without_leaking_details(setup):
    client, _, agent_id = setup
    app.dependency_overrides[get_llm] = lambda: FakeLLM(fail=True)

    conversation_id = await start_conversation(client, agent_id)
    response = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "Hello"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service temporarily unavailable"}


@pytest.mark.anyio
async def test_blank_message_is_rejected(setup):
    client, _, agent_id = setup
    app.dependency_overrides[get_llm] = lambda: FakeLLM()

    conversation_id = await start_conversation(client, agent_id)
    response = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"content": "    "},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_unknown_agent_returns_404(setup):
    client, _, _ = setup

    response = await client.post(
        "/v1/conversations", json={"agent_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404