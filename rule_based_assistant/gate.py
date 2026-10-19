# Thin deterministic gate over the rule engine.

from .config import HIGH_CONFIDENCE, RETRIEVAL_TOP_K
from .rule_engine import classify_utterance


def classify(utterance, top_k=RETRIEVAL_TOP_K):
    result = classify_utterance(utterance)
    candidates = result.get("candidates", [])
    if not candidates:
        return {
            "utterance": utterance,
            "intent": "unknown_intent",
            "confidence": 0.0,
            "candidates": [],
            "decision_type": "unknown_intent",
        }

    top_intent, top_score = candidates[0]
    if result.get("intent") in {"multiple_intents", "clarification_required"}:
        intent = result["intent"]
    elif top_score >= HIGH_CONFIDENCE:
        intent = top_intent
    else:
        intent = "unknown_intent"

    return {
        "utterance": utterance,
        "intent": intent,
        "confidence": top_score,
        "candidates": candidates,
        "decision_type": result.get("decision_type", "rule_match"),
        "matched_rules": result.get("matched_rules", []),
    }
