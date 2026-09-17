from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.knowledge import search_knowledge
from api.llm import LLMClient


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


def get_knowledge_search():
    return search_knowledge