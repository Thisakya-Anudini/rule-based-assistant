from rule_based_assistant import laya_adapter
from rule_based_assistant.rule_engine import classify_utterance
from rule_based_assistant.state_store import ConversationStateStore


def test_laya_is_disabled_by_default_and_preserves_rule_result(monkeypatch):
    monkeypatch.delenv("LAYA_ROUTER_ENABLED", raising=False)
    monkeypatch.setattr(
        laya_adapter,
        "_predict",
        lambda _utterance: (_ for _ in ()).throw(AssertionError("Laya should be disabled")),
    )
    rule_result = classify_utterance("where is my order")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "where is my order", rule_result
    )

    assert result is rule_result
    assert comparison["status"] == "disabled"
    assert comparison["selected_source"] == "rules"


def test_confident_laya_prediction_fills_unknown_rule_result(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LAYA_CONFIDENCE_THRESHOLD", "0.85")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("track_order", 0.91))
    rule_result = classify_utterance("I need a hand with something")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "I need a hand with something", rule_result
    )

    assert rule_result["intent"] == "unknown_intent"
    assert result["intent"] == "track_order"
    assert result["decision_type"] == "laya_fallback"
    assert comparison["status"] == "laya_fallback"
    assert comparison["selected_source"] == "laya_fallback"


def test_low_confidence_laya_prediction_keeps_unknown_rule_result(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("track_order", 0.6))
    rule_result = classify_utterance("I need a hand with something")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "I need a hand with something", rule_result
    )

    assert result is rule_result
    assert comparison["status"] == "below_confidence_threshold"


def test_rule_prediction_wins_when_laya_disagrees(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("cancel_order", 0.99))
    rule_result = classify_utterance("where is my order")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "where is my order", rule_result
    )

    assert result is rule_result
    assert comparison["status"] == "disagreement_rules_won"
    assert comparison["agreement"] is False


def test_unsupported_laya_intent_keeps_rule_result(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("shipment_question", 0.99))
    rule_result = classify_utterance("I need a hand with something")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "I need a hand with something", rule_result
    )

    assert result is rule_result
    assert comparison["status"] == "invalid_intent"


def test_laya_error_is_recorded_and_rules_continue(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")

    def fail_prediction(_text):
        raise RuntimeError("checkpoint unavailable")

    monkeypatch.setattr(laya_adapter, "_predict", fail_prediction)
    rule_result = classify_utterance("where is my order")

    result, comparison = laya_adapter.classify_with_optional_laya(
        "where is my order", rule_result
    )

    assert result is rule_result
    assert comparison["status"] == "error"
    assert comparison["error"] == "RuntimeError: checkpoint unavailable"


def test_state_store_uses_laya_fallback_and_keeps_comparison_in_trace(monkeypatch):
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("track_order", 0.9))
    store = ConversationStateStore()

    trace = store.process_utterance("I need a hand with something")

    assert trace["intent"] == "track_order"
    assert trace["decision_type"] == "laya_fallback"
    assert trace["model_comparison"]["rule_intent"] == "unknown_intent"
    assert trace["model_comparison"]["laya_intent"] == "track_order"
    assert store.frames[0].intent == "track_order"
