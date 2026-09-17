from voice.bot import VOICE_RULES, build_llm_settings, build_voice_prompt


def test_voice_prompt_keeps_agent_prompt_and_adds_voice_rules():
    prompt = build_voice_prompt("You are the NimbusCRM sales assistant.")

    assert prompt.startswith("You are the NimbusCRM sales assistant.")
    assert VOICE_RULES in prompt
    assert "Never use emojis" in prompt


def test_reasoning_effort_is_sent_through_extra_params():
    settings, label = build_llm_settings("openai/gpt-oss-20b", "prompt", "low")

    assert label == "low"
    assert settings.extra == {"reasoning_effort": "low"}


def test_no_reasoning_effort_uses_default_label():
    settings, label = build_llm_settings("openai/gpt-oss-20b", "prompt", None)

    assert label == "default"
    assert "reasoning_effort" not in settings.extra