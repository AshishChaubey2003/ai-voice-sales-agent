import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Lead

LEAD_CAPTURE_RULES = """Lead capture rules (these matter more than anything else in this conversation):
- If the visitor wants to be contacted (a call, a demo or more information from sales), collect their name and email. Company, team size and what they need are optional.
- Collect name and email only. Never ask for a phone number, an address or any other personal detail.
- Repeat the name and email back exactly and ask whether the sales team may contact them. When the visitor clearly says yes, you must call the save_lead tool. Do not continue the conversation without calling it.
- Never say that the sales team will contact them, reach out, get in touch or call. After save_lead returns "saved", say only that their details have been passed to the sales team.
- If save_lead returns "rejected", do exactly what the reason says.
- Never ask for passwords, card numbers or other sensitive data."""

SAVE_LEAD_TOOL = {
    "type": "function",
    "function": {
        "name": "save_lead",
        "description": (
            "Save the visitor's contact details for the sales team. Call only after the "
            "visitor has confirmed their name and email and agreed to be contacted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Visitor's name"},
                "email": {"type": "string", "description": "Visitor's email address"},
                "company": {"type": "string", "description": "Company name, if given"},
                "team_size": {
                    "type": "integer",
                    "description": "Number of people on the visitor's team, if given",
                },
                "need": {
                    "type": "string",
                    "description": "Short summary of what the visitor needs, if given",
                },
            },
            "required": ["name", "email"],
        },
    },
}

AFFIRMATIVE_START = re.compile(
    r"^(yes|yeah|yep|yup|sure|correct|right|ok|okay|confirm|confirmed|go ahead|"
    r"please do|that's right|that is right|haan|han|ji)\b"
)
NEGATIVE_WORDS = re.compile(r"\b(no|not|don't|dont|wait|wrong|change|stop)\b")


class LeadInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)
    team_size: int | None = Field(default=None, ge=1, le=100_000)
    need: str | None = Field(default=None, max_length=500)


def is_clear_yes(text: str) -> bool:
    cleaned = text.strip().lower().replace("\u2019", "'")
    if not cleaned or len(cleaned) > 80:
        return False
    if NEGATIVE_WORDS.search(cleaned):
        return False
    return bool(AFFIRMATIVE_START.match(cleaned))


def dialogue_turns(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        message
        for message in history
        if message.get("role") in ("user", "assistant")
        and isinstance(message.get("content"), str)
    ]


def consent_problem(history: list[dict[str, Any]], email: str) -> str | None:
    """Returns None when the visitor clearly agreed after hearing their details read back."""
    turns = dialogue_turns(history)
    if len(turns) < 2 or turns[-1]["role"] != "user":
        return "Read the name and email back to the visitor and ask for permission before saving."
    if turns[-2]["role"] != "assistant" or email.lower() not in turns[-2]["content"].lower():
        return (
            "Read the name and email back to the visitor and ask whether the sales team "
            "may contact them."
        )
    if not is_clear_yes(turns[-1]["content"]):
        return "The visitor has not clearly agreed yet. Ask them to confirm with a simple yes."
    return None


def parse_lead_arguments(arguments: str) -> tuple[LeadInput | None, str | None]:
    try:
        data = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return None, "The details could not be read. Ask the visitor for their name and email again."
    try:
        return LeadInput.model_validate(data), None
    except ValidationError:
        return None, "The name or email looks invalid. Ask the visitor to repeat it."


async def save_lead_from_tool(
    session: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    history: list[dict[str, Any]],
    arguments: str,
) -> dict[str, str]:
    lead_input, problem = parse_lead_arguments(arguments)
    if problem:
        return {"status": "rejected", "reason": problem}

    problem = consent_problem(history, str(lead_input.email))
    if problem:
        return {"status": "rejected", "reason": problem}

    turns = dialogue_turns(history)
    lead = await session.scalar(
        select(Lead).where(
            Lead.organization_id == organization_id,
            Lead.conversation_id == conversation_id,
        )
    )
    if lead is None:
        lead = Lead(organization_id=organization_id, conversation_id=conversation_id)
        session.add(lead)

    lead.name = lead_input.name
    lead.email = str(lead_input.email).lower()
    lead.company = lead_input.company
    lead.team_size = lead_input.team_size
    lead.need = lead_input.need
    lead.consent_prompt = turns[-2]["content"]
    lead.consent_reply = turns[-1]["content"]
    await session.flush()
    return {"status": "saved"}