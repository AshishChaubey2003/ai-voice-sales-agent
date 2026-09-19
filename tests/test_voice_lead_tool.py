from api.leads import SAVE_LEAD_TOOL
from voice.lead_tool import VOICE_LEAD_RULES, build_save_lead_schema


def test_voice_tool_schema_matches_the_shared_tool_definition():
    schema = build_save_lead_schema()
    function = SAVE_LEAD_TOOL["function"]

    assert schema.name == function["name"]
    assert schema.required == function["parameters"]["required"]
    assert set(schema.properties) == set(function["parameters"]["properties"])


def test_voice_rules_ask_the_visitor_to_spell_the_email():
    assert "spell" in VOICE_LEAD_RULES.lower()