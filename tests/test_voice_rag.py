from voice.rag import KNOWLEDGE_MARKER, is_knowledge_message, latest_user_text, with_knowledge


def test_latest_user_text_ignores_knowledge_messages():
    messages = [
        {"role": "assistant", "content": "Hi, how can I help?"},
        {"role": "user", "content": "How much is the Pro plan?"},
        {"role": "developer", "content": f"{KNOWLEDGE_MARKER}.\n\nold facts"},
    ]

    assert latest_user_text(messages) == "How much is the Pro plan?"


def test_latest_user_text_is_none_when_the_bot_spoke_last():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]

    assert latest_user_text(messages) is None


def test_with_knowledge_replaces_the_previous_knowledge_message():
    messages = [
        {"role": "user", "content": "Pro plan price?"},
        {"role": "developer", "content": f"{KNOWLEDGE_MARKER}.\n\nold facts"},
        {"role": "assistant", "content": "$29."},
        {"role": "user", "content": "And Business?"},
    ]

    updated = with_knowledge(messages, "Knowledge base:\n\n[1] Business plan\n$49")
    knowledge = [message for message in updated if is_knowledge_message(message)]

    assert len(knowledge) == 1
    assert "$49" in knowledge[0]["content"]
    assert updated[-1] is knowledge[0]