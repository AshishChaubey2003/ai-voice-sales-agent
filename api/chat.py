import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.deps import get_llm, get_session
from api.llm import LLMClient, LLMError
from api.models import Agent, Conversation, Message
from api.schemas import ChatReply, ConversationCreate, ConversationCreated, MessageCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.post("", response_model=ConversationCreated, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_session),
):
    agent = await session.scalar(
        select(Agent).where(Agent.id == payload.agent_id, Agent.status == "active")
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    conversation = Conversation(
        organization_id=agent.organization_id,
        agent_id=agent.id,
        channel="text",
    )
    session.add(conversation)
    await session.commit()
    return ConversationCreated(conversation_id=conversation.id)


@router.post("/{conversation_id}/messages", response_model=ChatReply)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    settings = get_settings()

    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.status == "active",
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    agent = await session.scalar(
        select(Agent).where(
            Agent.id == conversation.agent_id,
            Agent.organization_id == conversation.organization_id,
        )
    )

    session.add(
        Message(
            organization_id=conversation.organization_id,
            conversation_id=conversation.id,
            role="user",
            content=payload.content,
        )
    )
    await session.commit()

    recent = (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.organization_id == conversation.organization_id,
            )
            .order_by(Message.created_at.desc())
            .limit(settings.chat_history_limit)
        )
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]

    # LLM call kai second le sakta hai: tab tak DB transaction band rakho
    await session.commit()

    try:
        result = await llm.generate(agent.system_prompt, history)
    except LLMError:
        logger.exception("LLM call failed for conversation %s", conversation.id)
        raise HTTPException(
            status_code=503, detail="AI service temporarily unavailable"
        )

    session.add(
        Message(
            organization_id=conversation.organization_id,
            conversation_id=conversation.id,
            role="assistant",
            content=result.text,
            latency_ms={"llm": result.latency_ms},
        )
    )
    await session.commit()

    return ChatReply(
        conversation_id=conversation.id,
        reply=result.text,
        llm_latency_ms=result.latency_ms,
    )