import time
import uuid
from collections.abc import Callable

from loguru import logger
from pipecat.frames.frames import LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from api.knowledge import (
    QUERY_REWRITE_PROMPT,
    SearchResult,
    build_rewrite_input,
    clean_rewritten_query,
    format_knowledge_context,
    search_knowledge,
)
from api.llm import LLMClient, LLMError

KNOWLEDGE_MARKER = "Knowledge base for the visitor's latest message"

RetrievalCallback = Callable[[int, list[str], str | None], None]


def content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return " ".join(part for part in parts if part)
    return ""


def is_knowledge_message(message) -> bool:
    return (
        isinstance(message, dict)
        and message.get("role") == "developer"
        and isinstance(message.get("content"), str)
        and message["content"].startswith(KNOWLEDGE_MARKER)
    )


def is_tool_result(messages) -> bool:
    """True when the LLM is being re-run with a tool result, not a new visitor message."""
    last = messages[-1] if messages else None
    return isinstance(last, dict) and last.get("role") == "tool"


def conversation_turns(messages) -> list[dict[str, str]]:
    turns = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            continue
        text = content_to_text(message.get("content")).strip()
        if text:
            turns.append({"role": message["role"], "content": text})
    return turns


def latest_user_text(messages) -> str | None:
    turns = conversation_turns(messages)
    if not turns or turns[-1]["role"] != "user":
        return None
    return turns[-1]["content"]


def with_knowledge(messages, knowledge_text: str) -> list:
    cleaned = [message for message in messages if not is_knowledge_message(message)]
    return cleaned + [
        {"role": "developer", "content": f"{KNOWLEDGE_MARKER}.\n\n{knowledge_text}"}
    ]


def set_context_messages(context, messages) -> None:
    setter = getattr(context, "set_messages", None)
    if setter is not None:
        setter(messages)
    else:
        context.get_messages()[:] = messages


class KnowledgeInjector(FrameProcessor):
    """Adds company knowledge to the context right before the LLM answers."""

    def __init__(
        self,
        *,
        session_factory,
        organization_id: uuid.UUID,
        settings,
        rewriter: LLMClient | None,
        on_retrieval: RetrievalCallback,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._session_factory = session_factory
        self._organization_id = organization_id
        self._settings = settings
        self._rewriter = rewriter
        self._on_retrieval = on_retrieval

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            try:
                await self._inject(frame.context)
            except Exception:
                logger.exception("Knowledge injection failed; answering without knowledge")

        await self.push_frame(frame, direction)

    async def _inject(self, context) -> None:
        messages = list(context.get_messages())
        if is_tool_result(messages):
            return

        query = latest_user_text(messages)
        if not query:
            return

        start = time.perf_counter()
        search = await self._search(query)
        rewritten_query = None

        if not search.chunks and self._rewriter and len(conversation_turns(messages)) > 1:
            candidate = await self._rewrite(messages)
            if candidate and candidate.lower() != query.lower():
                retry = await self._search(candidate)
                if retry.chunks:
                    search = retry
                    rewritten_query = candidate

        set_context_messages(
            context, with_knowledge(messages, format_knowledge_context(search.chunks))
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        sources = [chunk.heading for chunk in search.chunks]
        logger.info(
            f"Knowledge search: {elapsed_ms} ms, sources={sources}, rewritten={rewritten_query!r}"
        )
        self._on_retrieval(elapsed_ms, sources, rewritten_query)

    async def _search(self, query: str) -> SearchResult:
        try:
            async with self._session_factory() as session:
                return await search_knowledge(
                    session,
                    self._organization_id,
                    query,
                    top_k=self._settings.rag_top_k,
                    max_distance=self._settings.rag_max_distance,
                )
        except Exception:
            logger.exception("Knowledge search failed")
            return SearchResult(chunks=[], elapsed_ms=0)

    async def _rewrite(self, messages) -> str:
        try:
            reply = await self._rewriter.generate(
                QUERY_REWRITE_PROMPT, build_rewrite_input(conversation_turns(messages))
            )
            return clean_rewritten_query(reply.text)
        except LLMError:
            logger.warning("Query rewrite failed")
            return ""