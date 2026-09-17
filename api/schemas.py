import uuid

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: uuid.UUID


class ConversationCreated(BaseModel):
    conversation_id: uuid.UUID


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=2000)


class ChatReply(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    llm_latency_ms: int
    sources: list[str] = Field(default_factory=list)