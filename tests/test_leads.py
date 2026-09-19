import pytest

from api.leads import consent_problem, is_clear_yes, parse_lead_arguments


@pytest.mark.parametrize(
    "text", ["Yes", "yes please", "Sure, go ahead", "Okay", "That's right", "haan"]
)
def test_clear_yes_is_accepted(text):
    assert is_clear_yes(text)


@pytest.mark.parametrize(
    "text", ["No", "Yes but change my email", "wait", "I'm not sure", "", "maybe later"]
)
def test_unclear_or_negative_reply_is_not_consent(text):
    assert not is_clear_yes(text)


def test_consent_requires_the_email_to_be_read_back_before_yes():
    history = [
        {"role": "user", "content": "I'm Rahul, rahul@example.com"},
        {"role": "assistant", "content": "Thanks! Anything else I can help with?"},
        {"role": "user", "content": "Yes"},
    ]

    assert consent_problem(history, "rahul@example.com") is not None


def test_consent_passes_after_read_back_and_clear_yes():
    history = [
        {"role": "user", "content": "I'm Rahul, rahul@example.com"},
        {
            "role": "assistant",
            "content": "To confirm: Rahul, Rahul@Example.com. May our sales team contact you?",
        },
        {"role": "user", "content": "yes"},
    ]

    assert consent_problem(history, "rahul@example.com") is None


def test_invalid_email_is_rejected():
    lead, problem = parse_lead_arguments('{"name": "Rahul", "email": "not-an-email"}')

    assert lead is None
    assert problem