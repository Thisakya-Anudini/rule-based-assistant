# Pre-flight for the web demo. Run this well before the session -- NOT live.

import sys


def check_imports():
    import dateparser  # noqa: F401
    import fastapi  # noqa: F401


def check_pipeline_end_to_end():
    from ..state_store import ConversationStateStore

    store = ConversationStateStore()
    store.process_utterance("Where is my order")
    trace = store.process_utterance("ORD-48213")
    calls = trace.get("tool_calls") or []
    if not calls or calls[0].get("tool") != "get_order_status":
        raise RuntimeError(f"expected a get_order_status tool call, got {calls!r}")
    if calls[0]["arguments"].get("order_id") != "ORD-48213":
        raise RuntimeError(f"order_id not extracted into the tool call: {calls[0]!r}")


CHECKS = [
    ("python deps import", check_imports),
    ("pipeline end-to-end: intent -> slot -> MCP call", check_pipeline_end_to_end),
]


def main():
    failed = False
    for name, fn in CHECKS:
        try:
            result = fn()
            extra = f"  ({result:.1f}s)" if isinstance(result, float) else ""
            print(f"  [ok]   {name}{extra}")
        except Exception as exc:
            failed = True
            print(f" [FAIL]  {name}\n         {type(exc).__name__}: {exc}")

    if failed:
        print("\nOne or more checks failed -- fix before the demo.")
        sys.exit(1)

    print("\nAll checks passed.")
    print("Start:  python -m uvicorn rule_based_assistant.server:app")
    print("Open:   http://127.0.0.1:8000/demo")


if __name__ == "__main__":
    main()
