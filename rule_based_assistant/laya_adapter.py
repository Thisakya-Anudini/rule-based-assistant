"""Optional Laya intent classification with deterministic rules as the authority."""

import math
import os
import threading
from functools import lru_cache

from . import call_log
from .intents import INTENTS

DEFAULT_CONFIDENCE_THRESHOLD = 0.85
_enabled_override = None
_settings_lock = threading.Lock()


def _enabled():
    with _settings_lock:
        override = _enabled_override
    if override is not None:
        return override
    value = os.getenv("LAYA_ROUTER_ENABLED", "false").strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise ValueError("LAYA_ROUTER_ENABLED must be true or false.")
    return value in {"true", "1", "yes", "on"}


def set_enabled(enabled):
    """Set the process-wide runtime override controlled by the demo."""
    if not isinstance(enabled, bool):
        raise TypeError("enabled must be a boolean.")
    global _enabled_override
    with _settings_lock:
        _enabled_override = enabled


def enabled():
    """Current process-wide Laya setting, including the environment default."""
    return _enabled()


def _confidence_threshold():
    raw_value = os.getenv("LAYA_CONFIDENCE_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD))
    try:
        threshold = float(raw_value)
    except ValueError as exc:
        raise ValueError("LAYA_CONFIDENCE_THRESHOLD must be a number between 0 and 1.") from exc
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("LAYA_CONFIDENCE_THRESHOLD must be a number between 0 and 1.")
    return threshold


@lru_cache(maxsize=1)
def _get_router():
    from laya import Router

    return Router()


def _questions():
    criteria = {}
    for intent, details in INTENTS.items():
        exemplars = details.get("exemplars", [])
        criteria[intent] = "; ".join(exemplars[:5]) or intent.replace("_", " ")
    return {
        "intent": {
            "type": "choice",
            "instructions": (
                "Choose the single best matching customer-support intent for the "
                "customer's message. Select only the intent that best describes "
                "the request; do not invent a label."
            ),
            "criteria": criteria,
        }
    }


def _predict(utterance):
    result = _get_router().predict({"body": utterance}, _questions())
    answer = result["answers"]["intent"]
    intent = answer["choice"]
    confidence = answer["answer_confidence"]
    if not isinstance(intent, str):
        raise ValueError("Laya returned a non-string intent.")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("Laya returned an invalid answer_confidence.")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Laya returned an answer_confidence outside 0..1.")
    return intent, confidence


def classify_with_optional_laya(utterance, rule_result):
    """Return the rule result, optionally using Laya only for unknown intents.

    The returned diagnostic is safe to include in the existing turn log. It does
    not contain the utterance itself; the API's existing turn record already does.
    """
    rule_candidates = rule_result.get("candidates", [])
    rule_intent = rule_result.get("intent", "unknown_intent")
    rule_score = float(rule_candidates[0][1]) if rule_candidates else 0.0
    comparison = {
        "enabled": False,
        "status": "disabled",
        "rule_intent": rule_intent,
        "rule_score": rule_score,
        "laya_intent": None,
        "laya_confidence": None,
        "agreement": None,
        "selected_source": "rules",
        "selected_intent": rule_intent,
    }

    if not _enabled():
        return rule_result, comparison

    comparison["enabled"] = True
    try:
        laya_intent, laya_confidence = _predict(utterance)
    except Exception as exc:
        comparison.update(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
        call_log.logger.exception("Laya intent prediction failed; retaining rule result")
        return rule_result, comparison

    valid_intent = laya_intent in INTENTS
    threshold = _confidence_threshold()
    comparison.update(
        status="compared",
        laya_intent=laya_intent,
        laya_confidence=laya_confidence,
        agreement=valid_intent and laya_intent == rule_intent,
    )

    if not valid_intent:
        comparison["status"] = "invalid_intent"
    elif rule_intent == "unknown_intent" and laya_confidence >= threshold:
        selected_result = {
            **rule_result,
            "intent": laya_intent,
            "score": laya_confidence,
            "candidates": [(laya_intent, laya_confidence)],
            "matched_rules": [],
            "decision_type": "laya_fallback",
            "message": None,
            "rule_hits": {},
        }
        comparison.update(
            selected_source="laya_fallback",
            selected_intent=laya_intent,
            status="laya_fallback",
        )
        return selected_result, comparison
    elif rule_intent == "unknown_intent":
        comparison["status"] = "below_confidence_threshold"
    elif laya_intent != rule_intent:
        comparison["status"] = "disagreement_rules_won"

    return rule_result, comparison
