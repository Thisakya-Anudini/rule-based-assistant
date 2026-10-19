# Turn/frame "views": stable presentation-ready state for the HTTP API and browser demo.

from .intents import INTENTS

DECISION_BY_TURN_TYPE = {
    "new_intent": "accepted",
    "multi_intent_blocked": "multi_intent",
    "slot_fill": "slot_fill",
    "unresolved_continuation": "continuation",
    "ambiguous_continuation": "continuation",
    "correction": "correction",
    "unknown_intent": "unknown",
    "clarification_required": "clarification",
    "duplicate_suppressed": "duplicate",
    "slot_override": "override",
}


def slot_display(value):
    if isinstance(value, dict) and "date" in value:
        return value["date"]
    return value


def to_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        return to_jsonable(obj.item())
    return str(obj)


def frame_view(frame, filled_this_turn=()):
    return {
        "id": frame.id,
        "intent": frame.intent,
        "status": frame.status,
        "initiated_by": frame.initiated_by,
        "required": INTENTS.get(frame.intent, {}).get("required_slots", []),
        "slots": {k: slot_display(v) for k, v in frame.slots.items()},
        "missing": list(frame.missing_slots),
        "filled_this_turn": list(filled_this_turn),
        "tool_call": frame.tool_call,
        "tool_result": frame.tool_result,
    }


def frames_view(store, filled_this_turn=(), focus_frame_id=None):
    return [
        frame_view(f, filled_this_turn if f.id == focus_frame_id else ())
        for f in store.frames
    ]


def all_tool_calls(store):
    return [
        {"frame": f.id, "intent": f.intent, **f.tool_call}
        for f in store.frames
        if f.tool_call
    ]


def build_turn_view(trace, store, turn_index):
    turn_type = trace.get("turn_type", "unknown_intent")
    candidates = [
        {"intent": name, "score": round(float(score), 3)}
        for name, score in trace.get("candidates", [])
    ]

    selected = trace.get("intent")
    if selected is None and turn_type == "multi_intent_blocked":
        selected = " + ".join(trace.get("intents", [])) or None
    elif selected is None and "frame" in trace:
        frame = store.get_frame(trace["frame"])
        selected = frame.intent if frame else None

    clarification = None
    if trace.get("decision_type") == "clarification_required":
        clarification = {
            "reason": "close_rule_matches",
            "candidate_intents": [name for name, _ in trace.get("candidates", [])],
            "message": trace.get("message"),
        }

    filled = trace.get("filled_slots", []) or []
    return {
        "turn_index": turn_index,
        "utterance": trace.get("utterance", ""),
        "speaker": trace.get("speaker", "customer"),
        "intent": {
            "turn_type": turn_type,
            "decision": DECISION_BY_TURN_TYPE.get(turn_type, turn_type),
            "selected_intent": selected,
            "top_score": candidates[0]["score"] if candidates else None,
            "candidates": candidates,
            "heuristic_flags": trace.get("heuristic_flags", []),
            "decision_type": trace.get("decision_type", turn_type),
            "matched_rules": trace.get("matched_rules", []),
            "clarification": clarification,
            "message": trace.get("message"),
            "model_comparison": trace.get("model_comparison"),
        },
        "slots": {"frames": frames_view(store, filled, trace.get("frame"))},
        "mcp": {
            "fired_this_turn": to_jsonable(trace.get("tool_calls", [])),
            "all_calls": all_tool_calls(store),
        },
    }


def build_override_trace(frame, slot_name, refired):
    trace = {
        "utterance": f"Corrected {slot_name} to {slot_display(frame.slots[slot_name])!r}",
        "speaker": "agent",
        "candidates": [],
        "heuristic_flags": ["override"],
        "turn_type": "slot_override",
        "intent": frame.intent,
        "frame": frame.id,
        "filled_slots": [slot_name],
    }
    if refired:
        trace["tool_calls"] = [frame.tool_call]
    return trace
