import json
import uuid
from collections.abc import Callable

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from api.leads import SAVE_LEAD_TOOL, save_lead_from_tool
from voice.rag import conversation_turns

VOICE_LEAD_RULES = """Voice lead capture rules:
- Email addresses are easy to mishear. Ask the visitor to spell the part before the @ sign letter by letter, then read the full address back slowly and ask if it is correct.
- If the visitor corrects any detail, read the corrected version back again before saving.
- Keep each of these steps to one short sentence."""


def build_save_lead_schema() -> FunctionSchema:
    function = SAVE_LEAD_TOOL["function"]
    return FunctionSchema(
        name=function["name"],
        description=function["description"],
        properties=function["parameters"]["properties"],
        required=function["parameters"]["required"],
    )


def build_save_lead_handler(
    *,
    session_factory,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    on_result: Callable[[str], None] | None = None,
):
    """Pipecat calls this when the LLM asks for save_lead; the consent gate still decides."""

    async def handler(params: FunctionCallParams) -> None:
        history = conversation_turns(params.context.get_messages())
        try:
            async with session_factory() as session:
                outcome = await save_lead_from_tool(
                    session,
                    organization_id,
                    conversation_id,
                    history,
                    json.dumps(dict(params.arguments)),
                )
                if outcome["status"] == "saved":
                    await session.commit()
        except Exception:
            logger.exception("save_lead failed")
            outcome = {
                "status": "rejected",
                "reason": "The details could not be saved right now. Apologise and offer to try again.",
            }

        logger.info(f"save_lead: {outcome}")
        if on_result:
            on_result(outcome["status"])
        await params.result_callback(outcome)

    return handler