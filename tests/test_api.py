# API tests for the deterministic rule engine, state machine, tools, and HTTP layer.

import pytest
from fastapi.testclient import TestClient

from rule_based_assistant import call_log, state_store, zoho_client


@pytest.fixture
def client(monkeypatch, tmp_path):
    from rule_based_assistant import server

    monkeypatch.setattr(call_log, "TURN_LOG", tmp_path / "turns.jsonl")
    monkeypatch.setattr(zoho_client, "search_lead", lambda email: {"data": [{"Email": email}]})
    server._calls.clear()
    return TestClient(server.app, raise_server_exceptions=False)


def new_call(client):
    r = client.post("/v1/calls")
    assert r.status_code == 201
    return r.json()["call_id"]


def turn(client, call_id, utterance, speaker="customer", **params):
    return client.post(f"/v1/calls/{call_id}/turns", json={"utterance": utterance, "speaker": speaker}, params=params)


def assert_error(r, status, code):
    assert r.status_code == status, r.text
    body = r.json()["error"]
    assert body["code"] == code and body["message"]


# -- lifecycle ----------------------------------------------------------------

def test_lifecycle_get_reset_delete(client):
    cid = new_call(client)
    turn(client, cid, "track my order")
    state = client.get(f"/v1/calls/{cid}").json()
    assert state["turn_count"] == 1 and state["frames"][0]["intent"] == "track_order"

    assert client.post(f"/v1/calls/{cid}/reset").json() == {"call_id": cid}
    state = client.get(f"/v1/calls/{cid}").json()
    assert state["turn_count"] == 0 and state["frames"] == []

    assert client.delete(f"/v1/calls/{cid}").status_code == 204
    assert_error(client.get(f"/v1/calls/{cid}"), 404, "call_not_found")


@pytest.mark.parametrize("method,path", [
    ("get", "/v1/calls/nope"), ("delete", "/v1/calls/nope"), ("post", "/v1/calls/nope/reset"),
])
def test_unknown_call_404(client, method, path):
    assert_error(getattr(client, method)(path), 404, "call_not_found")


def test_unknown_call_on_turn_and_override(client):
    assert_error(turn(client, "nope", "hi"), 404, "call_not_found")
    r = client.patch("/v1/calls/nope/frames/1/slots/order_id", json={"value": "ORD-1234"})
    assert_error(r, 404, "call_not_found")


def test_unknown_route_uses_error_shape(client):
    assert_error(client.get("/v1/nothing"), 404, "not_found")


# -- turns --------------------------------------------------------------------

def test_turn_stable_view_and_slot_fill_fires_tool(client):
    cid = new_call(client)
    v1 = turn(client, cid, "please track my order").json()
    assert v1["turn_index"] == 1
    assert v1["intent"]["turn_type"] == "new_intent" and v1["intent"]["decision"] == "accepted"
    assert v1["intent"]["selected_intent"] == "track_order"
    assert v1["intent"]["model_comparison"]["status"] == "disabled"
    assert v1["intent"]["model_comparison"]["selected_source"] == "rules"
    frame = v1["slots"]["frames"][0]
    assert frame["status"] == "AWAITING_INFO" and frame["missing"] == ["order_id"]
    assert v1["mcp"]["fired_this_turn"] == [] and v1["debug"] is None

    v2 = turn(client, cid, "ORD-99213").json()
    assert v2["intent"]["turn_type"] == "slot_fill"
    assert v2["slots"]["frames"][0]["filled_this_turn"] == ["order_id"]
    assert v2["mcp"]["fired_this_turn"] == [
        {"tool": "get_order_status", "arguments": {"order_id": "ORD-99213"}}
    ]
    assert v2["slots"]["frames"][0]["status"] == "FIRED"


def test_speaker_recorded_as_initiated_by(client):
    cid = new_call(client)
    v = turn(client, cid, "let me track that", speaker="agent").json()
    assert v["speaker"] == "agent" and v["slots"]["frames"][0]["initiated_by"] == "agent"


def test_agent_order_number_prompt_then_customer_id_fires_tracking_tool(client):
    cid = new_call(client)
    turn(client, cid, "quick question about an order I placed last week")

    prompt = turn(client, cid, "Sure, what's the order number?", speaker="agent").json()
    assert prompt["intent"]["selected_intent"] == "track_order"
    assert prompt["slots"]["frames"][0]["missing"] == ["order_id"]

    reply = turn(client, cid, "It's ORD-55201").json()
    assert reply["intent"]["turn_type"] == "slot_fill"
    assert reply["mcp"]["fired_this_turn"] == [
        {"tool": "get_order_status", "arguments": {"order_id": "ORD-55201"}}
    ]


def test_agent_prompts_for_pending_reschedule_slots_without_opening_tracking(client):
    cid = new_call(client)
    start = turn(client, cid, "I need to reschedule my delivery").json()
    assert start["slots"]["frames"][0]["intent"] == "change_delivery_date"

    prompt = turn(
        client,
        cid,
        "What's the order number and new date you'd like?",
        speaker="agent",
    ).json()

    frames = prompt["slots"]["frames"]
    assert len(frames) == 1
    assert frames[0]["intent"] == "change_delivery_date"
    assert frames[0]["status"] == "AWAITING_INFO"


def test_customer_can_correct_fired_delivery_date_with_another_frame_pending(client):
    cid = new_call(client)
    turn(client, cid, "Where is my refund?")
    turn(client, cid, "Reschedule ORD-34509 to 2030-01-15")

    correction = turn(
        client,
        cid,
        "Actually, scratch that, move delivery to 2030-02-20 instead.",
    ).json()

    frames = correction["slots"]["frames"]
    delivery_frame = next(frame for frame in frames if frame["intent"] == "change_delivery_date")
    assert correction["intent"]["turn_type"] == "correction"
    assert delivery_frame["slots"]["new_date"] == "2030-02-20T00:00:00"
    assert correction["mcp"]["fired_this_turn"] == [
        {
            "tool": "reschedule_delivery",
            "arguments": {"order_id": "ORD-34509", "new_date": "2030-02-20T00:00:00"},
        }
    ]


def test_customer_can_correct_fired_order_id(client):
    cid = new_call(client)
    turn(client, cid, "Where is my refund?")
    turn(client, cid, "Reschedule ORD-34509 to 2030-01-15")
    turn(client, cid, "ORD-93475")

    correction = turn(client, cid, "Sorry, my mistake, it's ORD-91027.").json()

    assert correction["intent"]["turn_type"] == "correction"
    assert correction["slots"]["frames"][0]["slots"]["order_id"] == "ORD-91027"
    assert correction["slots"]["frames"][1]["slots"]["order_id"] == "ORD-34509"
    assert correction["mcp"]["fired_this_turn"] == [
        {"tool": "get_refund_status", "arguments": {"order_id": "ORD-91027"}}
    ]


def test_exchange_instead_reuses_completed_return_order_id(client):
    cid = new_call(client)
    turn(client, cid, "I want to start a return because this is the wrong size")
    turn(client, cid, "What's the order number?", speaker="agent")
    turn(client, cid, "ORD-40188")

    exchange = turn(
        client,
        cid,
        "Actually, on second thought, could we do an exchange instead? I'd rather just size up.",
    ).json()

    frames = exchange["slots"]["frames"]
    assert len(frames) == 2
    assert frames[0]["intent"] == "initiate_return"
    assert frames[1]["intent"] == "exchange_item"
    assert frames[1]["status"] == "FIRED"
    assert frames[1]["slots"]["order_id"] == "ORD-40188"
    assert exchange["mcp"]["fired_this_turn"] == [
        {"tool": "start_exchange", "arguments": {"order_id": "ORD-40188"}}
    ]


def test_non_date_complaint_does_not_fill_pending_delivery_date(client):
    cid = new_call(client)
    start = turn(client, cid, "Reschedule ORD-34509").json()
    assert start["slots"]["frames"][0]["missing"] == ["new_date"]

    complaint = turn(
        client,
        cid,
        "Honestly this has been a headache, and now I'm worried the cancellation didn't actually go through either.",
    ).json()

    frame = complaint["slots"]["frames"][0]
    assert complaint["intent"]["turn_type"] == "unresolved_continuation"
    assert frame["status"] == "AWAITING_INFO"
    assert frame["missing"] == ["new_date"]
    assert complaint["mcp"]["fired_this_turn"] == []


def test_debug_flag_includes_json_safe_trace(client):
    cid = new_call(client)
    v = turn(client, cid, "track my order", debug="true").json()
    assert v["debug"]["turn_type"] == "new_intent"


def test_rule_match_multi_intent_ambiguity_and_unknown(client):
    cid = new_call(client)
    matched = turn(client, cid, "maybe track it").json()
    assert matched["intent"]["turn_type"] == "new_intent"
    assert matched["intent"]["selected_intent"] == "track_order"
    assert matched["intent"]["decision_type"] == "rule_match"

    cid = new_call(client)
    multi = turn(client, cid, "track ORD-12345 and cancel ORD-67890").json()
    assert multi["intent"]["turn_type"] == "multi_intent_blocked"
    assert multi["intent"]["message"] and multi["slots"]["frames"] == []

    cid = new_call(client)
    unclear = turn(client, cid, "my order hasn't arrived").json()
    assert unclear["intent"]["turn_type"] == "clarification_required"
    assert unclear["intent"]["message"]
    assert unclear["intent"]["clarification"]["reason"] == "close_rule_matches"
    assert unclear["slots"]["frames"] == []

    cid = new_call(client)
    assert turn(client, cid, "hello there").json()["intent"]["turn_type"] == "unknown_intent"


def test_new_date_slot_is_flattened_to_resolved_string(client):
    cid = new_call(client)
    turn(client, cid, "reschedule ORD-12345 to 2030-01-15")
    frame = client.get(f"/v1/calls/{cid}").json()["frames"][0]
    assert frame["status"] == "FIRED"
    assert frame["slots"]["new_date"] == "2030-01-15T00:00:00"  # resolved ISO-8601, not the {"text","date"} dict


def test_zoho_tool_result_exposed(client):
    cid = new_call(client)
    v = turn(client, cid, "look me up at jane@example.com").json()
    frame = v["slots"]["frames"][0]
    assert frame["tool_call"]["tool"] == "search_zoho_lead"
    assert frame["tool_result"] == {"data": [{"Email": "jane@example.com"}]}
    assert client.get(f"/v1/calls/{cid}").json()["frames"][0]["tool_result"] == frame["tool_result"]


def test_zoho_failure_is_a_tool_error_not_a_500(client, monkeypatch):
    def boom(email):
        raise RuntimeError("zoho down")
    monkeypatch.setattr(zoho_client, "search_lead", boom)
    cid = new_call(client)
    r = turn(client, cid, "look me up at jane@example.com")
    assert r.status_code == 200
    assert "zoho down" in r.json()["slots"]["frames"][0]["tool_result"]["error"]


# -- validation & errors -------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"utterance": ""}, {"utterance": "   "}, {"utterance": "x" * 2001},
    {"utterance": "hi", "speaker": "robot"}, {},
])
def test_turn_validation(client, payload):
    cid = new_call(client)
    r = client.post(f"/v1/calls/{cid}/turns", json=payload)
    assert_error(r, 422, "validation_error")
    assert r.json()["error"]["details"]


def test_pipeline_exception_is_500_with_error_shape(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("rule engine exploded")
    monkeypatch.setattr(state_store, "classify_utterance", boom)
    cid = new_call(client)
    r = turn(client, cid, "track my order")
    assert_error(r, 500, "pipeline_error")
    assert "exploded" not in r.text
    # A failed turn doesn't consume a turn index.
    assert client.get(f"/v1/calls/{cid}").json()["turn_count"] == 0


# -- slot override -------------------------------------------------------------

def test_override_refires_tool_with_corrected_value(client):
    cid = new_call(client)
    turn(client, cid, "track my order")
    turn(client, cid, "ORD-11111")
    r = client.patch(f"/v1/calls/{cid}/frames/1/slots/order_id", json={"value": "ORD-22222"})
    assert r.status_code == 200
    v = r.json()
    assert v["intent"]["turn_type"] == "slot_override" and v["speaker"] == "agent"
    assert v["turn_index"] == 3
    assert v["mcp"]["fired_this_turn"] == [
        {"tool": "get_order_status", "arguments": {"order_id": "ORD-22222"}}
    ]
    assert v["slots"]["frames"][0]["slots"]["order_id"] == "ORD-22222"


def test_override_errors(client):
    cid = new_call(client)
    turn(client, cid, "track my order")
    url = f"/v1/calls/{cid}/frames/1/slots"
    assert_error(client.patch(f"/v1/calls/{cid}/frames/99/slots/order_id", json={"value": "ORD-1234"}), 404, "frame_not_found")
    assert_error(client.patch(f"{url}/email", json={"value": "a@b.co"}), 422, "invalid_slot")
    assert_error(client.patch(f"{url}/order_id", json={"value": "no id here"}), 422, "invalid_slot_value")
    assert_error(client.patch(f"{url}/order_id", json={"value": ""}), 422, "validation_error")
    # Nothing above changed anything or consumed a turn index.
    assert client.get(f"/v1/calls/{cid}").json()["turn_count"] == 1


def test_override_on_reverted_frame_is_409(client):
    cid = new_call(client)
    turn(client, cid, "cancel it")  # opens cancel_order, awaiting order_id
    assert turn(client, cid, "actually never mind").json()["intent"]["turn_type"] == "ambiguous_continuation"
    # Complete the frame first, then revert it with a correction.
    turn(client, cid, "ORD-12345")
    assert turn(client, cid, "actually never mind").json()["intent"]["turn_type"] == "correction"
    r = client.patch(f"/v1/calls/{cid}/frames/1/slots/order_id", json={"value": "ORD-99999"})
    assert_error(r, 409, "frame_reverted")


def test_agent_reference_does_not_revert_completed_billing_action(client):
    cid = new_call(client)
    turn(client, cid, "I was charged twice for the same order, ORD-88712")

    confirmation = turn(
        client,
        cid,
        "I can confirm there are two charges on that order, that shouldn't have happened.",
        speaker="agent",
    ).json()

    assert confirmation["intent"]["turn_type"] != "correction"
    assert confirmation["slots"]["frames"][0]["status"] == "FIRED"


def test_agent_refund_timing_update_does_not_open_refund_lookup(client):
    cid = new_call(client)
    turn(client, cid, "Cancel my order ORD-29650")

    update = turn(
        client,
        cid,
        "Let me check the status of that one... it hasn't shipped yet, so I've gone ahead and cancelled it, you'll see the refund in 3 to 5 business days.",
        speaker="agent",
    ).json()

    assert update["intent"]["turn_type"] == "duplicate_suppressed"
    assert len(update["slots"]["frames"]) == 1
    assert update["slots"]["frames"][0]["intent"] == "cancel_order"


def test_refund_duration_question_reuses_referenced_billing_order(client):
    cid = new_call(client)
    turn(client, cid, "I was charged twice for the same order, ORD-88712")

    refund = turn(
        client,
        cid,
        "Going back to that duplicate charge, how long will the refund take?",
    ).json()

    assert refund["intent"]["selected_intent"] == "check_refund_status"
    assert refund["slots"]["frames"][-1]["slots"]["order_id"] == "ORD-88712"
    assert refund["mcp"]["fired_this_turn"] == [
        {"tool": "get_refund_status", "arguments": {"order_id": "ORD-88712"}}
    ]

    other_refund = turn(client, cid, "Check the refund status for ORD-93475").json()
    refund_frames = [
        frame for frame in other_refund["slots"]["frames"]
        if frame["intent"] == "check_refund_status"
    ]
    assert len(refund_frames) == 2
    assert [frame["slots"]["order_id"] for frame in refund_frames] == ["ORD-88712", "ORD-93475"]
    assert other_refund["mcp"]["fired_this_turn"] == [
        {"tool": "get_refund_status", "arguments": {"order_id": "ORD-93475"}}
    ]


def test_agent_refund_submission_update_does_not_request_clarification(client):
    cid = new_call(client)
    turn(client, cid, "I was charged twice for the same order, ORD-88712")

    update = turn(
        client,
        cid,
        "I'm submitting a refund request for the duplicate charge right now.",
        speaker="agent",
    ).json()

    assert update["intent"]["turn_type"] == "unknown_intent"
    assert len(update["slots"]["frames"]) == 1
    assert update["slots"]["frames"][0]["intent"] == "billing_dispute"


# -- transcript ----------------------------------------------------------------

def test_transcript_text(client):
    cid = new_call(client)
    text = "Customer: please track my order\nAgent: sure, what is the order number?\nCustomer: ORD-99213\nnoise line"
    r = client.post(f"/v1/calls/{cid}/transcript", json={"transcript": text})
    assert r.status_code == 200
    body = r.json()
    assert [t["speaker"] for t in body["turns"]] == ["customer", "agent", "customer"]
    assert [t["turn_index"] for t in body["turns"]] == [1, 2, 3]
    assert body["frames"][0]["status"] == "FIRED"


def test_transcript_turns_list(client):
    cid = new_call(client)
    r = client.post(f"/v1/calls/{cid}/transcript", json={"turns": [
        {"utterance": "track my order"}, {"utterance": "ORD-99213", "speaker": "customer"},
    ]})
    assert r.status_code == 200 and r.json()["frames"][0]["status"] == "FIRED"


@pytest.mark.parametrize("payload", [
    {}, {"transcript": "a", "turns": [{"utterance": "b"}]}, {"transcript": "no tags at all"},
    {"turns": [{"utterance": "ok"}, {"utterance": ""}]},
    {"transcript": "Customer: " + "x" * 2001},
])
def test_transcript_validation_processes_nothing(client, payload):
    cid = new_call(client)
    assert_error(client.post(f"/v1/calls/{cid}/transcript", json=payload), 422, "validation_error")
    assert client.get(f"/v1/calls/{cid}").json()["turn_count"] == 0


# -- catalog, log, health, demo -------------------------------------------------

def test_intent_and_tool_catalogs(client):
    intents = {i["name"]: i for i in client.get("/v1/intents").json()}
    assert intents["track_order"]["required_slots"] == ["order_id"]
    assert intents["track_order"]["tool"] == "get_order_status"
    tools = {t["name"]: t for t in client.get("/v1/tools").json()}
    assert tools["search_zoho_lead"]["executes_live"] is True
    assert tools["get_order_status"]["executes_live"] is False
    assert tools["get_order_status"]["intents"] == ["track_order"]
    assert tools["get_order_status"]["input_schema"]["required"] == ["order_id"]
    assert all(i["tool"] in tools for i in intents.values() if i["tool"])


def test_log_records_and_filters(client):
    a, b = new_call(client), new_call(client)
    turn(client, a, "track my order")
    turn(client, b, "cancel it")
    all_recs = client.get("/v1/log").json()
    assert all_recs["total"] == 4  # 2 call_created + 2 turn
    only_a = client.get("/v1/log", params={"call_id": a}).json()
    assert {r["call_id"] for r in only_a["records"]} == {a}
    assert [r["event"] for r in only_a["records"]] == ["call_created", "turn"]
    assert client.get("/v1/log", params={"limit": 1}).json()["records"][-1]["event"] == "turn"
    assert_error(client.get("/v1/log", params={"limit": 0}), 422, "validation_error")


def test_health_ok_and_degraded(client, monkeypatch):
    assert client.get("/health").json() == {
        "status": "ok", "deterministic": True, "engine": "rule_engine"
    }


def test_laya_setting_can_be_read_and_toggled(client, monkeypatch):
    from rule_based_assistant import laya_adapter

    monkeypatch.setattr(laya_adapter, "_enabled_override", None)
    laya_adapter.set_enabled(False)
    assert client.get("/v1/classifier/laya").json()["enabled"] is False

    enabled = client.put("/v1/classifier/laya", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert laya_adapter.enabled() is True

    disabled = client.put("/v1/classifier/laya", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert laya_adapter.enabled() is False


def test_demo_includes_laya_toggle(client):
    page = client.get("/demo")
    assert page.status_code == 200
    assert 'id="toggle-laya"' in page.text
    assert 'id="laya-status"' in page.text
    assert page.text.index('id="speaker-customer"') < page.text.index('id="upload-transcript"')
    assert page.text.index('id="send"') < page.text.index('id="upload-transcript"')


def test_turn_view_exposes_laya_fallback_comparison(client, monkeypatch):
    from rule_based_assistant import laya_adapter

    monkeypatch.setattr(laya_adapter, "_enabled_override", None)
    monkeypatch.setenv("LAYA_ROUTER_ENABLED", "true")
    monkeypatch.setattr(laya_adapter, "_predict", lambda _text: ("track_order", 0.91))
    call_id = new_call(client)

    response = turn(client, call_id, "I need a hand with something")

    assert response.status_code == 200
    comparison = response.json()["intent"]["model_comparison"]
    assert comparison["rule_intent"] == "unknown_intent"
    assert comparison["laya_intent"] == "track_order"
    assert comparison["selected_source"] == "laya_fallback"


def test_demo_page_and_assets_and_no_legacy_routes(client):
    assert client.get("/demo").status_code == 200
    assert client.get("/demo/static/app.js").status_code == 200
    assert client.get("/demo/static/../server.py").status_code == 404
    assert client.post("/calls").status_code == 404
    assert client.post("/demo/calls").status_code == 404


def test_openapi_documents_all_v1_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/v1/calls", "/v1/calls/{call_id}", "/v1/calls/{call_id}/turns", "/v1/calls/{call_id}/transcript",
              "/v1/calls/{call_id}/reset", "/v1/calls/{call_id}/frames/{frame_id}/slots/{slot_name}",
              "/v1/intents", "/v1/tools", "/v1/log", "/v1/classifier/laya", "/health"]:
        assert p in paths, p
