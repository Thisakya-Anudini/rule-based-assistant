import pytest

from rule_based_assistant.rule_engine import classify_utterance, retrieve_intents


@pytest.mark.parametrize(
    "utterance, expected",
    [
        ("where is my order", "track_order"),
        ("cancel my order", "cancel_order"),
        ("what payment methods do you accept", "payment_info"),
        ("my package arrived damaged", "report_delivery_problem"),
        ("I want to speak to a supervisor or a real person", "request_human_agent"),
        ("I'll log a formal complaint on your account", "file_complaint"),
        ("tell me a joke", "unknown_intent"),
    ],
)
def test_rule_based_classification(utterance, expected):
    result = classify_utterance(utterance)
    assert result["intent"] == expected


def test_ambiguous_message_requires_clarification():
    result = classify_utterance("my order hasn't arrived")
    assert result["intent"] == "clarification_required"
    candidate_names = {name for name, _score in result["candidates"]}
    assert "track_order" in candidate_names
    assert "report_delivery_problem" in candidate_names
    assert result["matched_rules"]


def test_multi_intent_message_is_detected():
    result = classify_utterance("track ORD-12345 and cancel ORD-67890")
    assert result["intent"] == "multiple_intents"
    candidate_names = {name for name, _score in result["candidates"]}
    assert "track_order" in candidate_names
    assert "cancel_order" in candidate_names


def test_retrieval_returns_ranked_candidates():
    ranked = retrieve_intents("where is my order", top_k=3)
    assert ranked[0][0] == "track_order"
    assert 0.5 <= ranked[0][1] <= 1.0
    assert all(name and 0.0 <= score <= 1.0 for name, score in ranked)
