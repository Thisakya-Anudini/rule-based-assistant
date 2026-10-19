# Demo runner for interactive and replay-based conversation flows.
# The runtime API lives in server.py; this file is a local test harness.

import argparse
import glob
import os
import re
import sys
import time

from ..gate import classify
from ..state_store import ConversationStateStore

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SAMPLES_DIR = os.path.join(REPO_ROOT, "samples")
DATASET_PATH = os.path.join(REPO_ROOT, "intent_test_dataset.xlsx")
RESULTS_PATH = os.path.join(REPO_ROOT, "intent_test_results.xlsx")

CUSTOMER_SPEAK_SECONDS = 2.0
AGENT_SPEAK_SECONDS = 1.0
THINKING_SECONDS = 0.4

_TURN_RE = re.compile(r"^(Customer|Agent):\s*(.*)$", re.IGNORECASE)


def parse_turn(line):
    match = _TURN_RE.match(line.strip())
    if not match:
        return None
    speaker, utterance = match.group(1).capitalize(), match.group(2).strip()
    return (speaker, utterance) if utterance else None


def parse_turns(text):
    turns = []
    for line in text.splitlines():
        turn = parse_turn(line)
        if turn:
            turns.append(turn)
    return turns


def warm_up():
    print("Checking deterministic rules...", end=" ", flush=True)
    ConversationStateStore().process_utterance("warm up")
    print("done.\n")


def print_trace(trace):
    cand_str = ", ".join(f"{intent}={score:.2f}" for intent, score in trace["candidates"])
    print(f"    candidates: {cand_str}")
    if trace.get("heuristic_flags"):
        print(f"    flags: {', '.join(trace['heuristic_flags'])}")
    print(f"    turn_type: {trace['turn_type']}")
    if trace.get("decision_type") == "clarification_required":
        print(f"    -> clarification: {trace.get('message')}")
    if trace.get("frames"):
        print(f"    frames opened: {trace['frames']}")
    elif "frame" in trace:
        extra = f" filled: {trace['filled_slots']}" if trace.get("filled_slots") else ""
        print(f"    frame #{trace['frame']}{extra}")
    for call in trace.get("tool_calls", []):
        args = ", ".join(f"{k}={v!r}" for k, v in call["arguments"].items())
        print(f"    -> tool call: {call['tool']}({args})")


def print_frames(store):
    print("\n  Final conversation state:")
    if not store.frames:
        print("    (no frames opened)")
    for frame in store.frames:
        origin = f" ({frame.initiated_by})" if frame.initiated_by != "customer" else ""
        print(
            f"    #{frame.id} {frame.intent}{origin} [{frame.status}] "
            f"slots={frame.slots} missing={frame.missing_slots}"
        )
        if frame.tool_call:
            args = ", ".join(f"{k}={v!r}" for k, v in frame.tool_call["arguments"].items())
            print(f"        tool call: {frame.tool_call['tool']}({args})")


def run_call(path):
    with open(path, "r", encoding="utf-8") as f:
        turns = parse_turns(f.read())

    print("=" * 70)
    print(f"Incoming call: {os.path.basename(path)}")
    print("=" * 70)

    store = ConversationStateStore()
    for speaker, utterance in turns:
        delay = CUSTOMER_SPEAK_SECONDS if speaker == "Customer" else AGENT_SPEAK_SECONDS
        print(f"\n[{speaker} speaking...]", end="", flush=True)
        time.sleep(delay)
        print(f"\r{speaker}: {utterance}" + " " * 20)

        print("  [analyzing...]", end="", flush=True)
        time.sleep(THINKING_SECONDS)
        print("\r" + " " * 20 + "\r", end="")
        trace = store.process_utterance(utterance, speaker=speaker.lower())
        print_trace(trace)

    print_frames(store)
    print()


def run_calls(names):
    if names:
        paths = [n if os.path.dirname(n) else os.path.join(SAMPLES_DIR, n) for n in names]
    else:
        paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "convo*.txt")))
    if not paths:
        print("No sample transcripts found (expected samples/convo*.txt).")
        return
    for path in paths:
        run_call(path)


def interactive_loop():
    print(
        'Type turns tagged the same way a transcript is: "Customer: ..." or '
        '"Agent: ...". State persists across turns. Ctrl+C to quit.\n'
    )
    store = ConversationStateStore()
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        turn = parse_turn(line)
        if turn is None:
            print('  (ignored -- prefix the line with "Customer: " or "Agent: ")')
            continue
        speaker, utterance = turn

        start = time.perf_counter()
        trace = store.process_utterance(utterance, speaker=speaker.lower())
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"  ({elapsed_ms:.1f} ms)")
        print_trace(trace)
        print()
    print_frames(store)


def run_test(dataset_path=DATASET_PATH, results_path=RESULTS_PATH):
    import pandas as pd

    df = pd.read_excel(dataset_path)

    predicted_intents = []
    correct_flags = []
    elapsed_times_ms = []

    for utterance, expected in zip(df["Utterance"], df["Expected Intent"]):
        start = time.perf_counter()
        result = classify(utterance)
        elapsed_ms = (time.perf_counter() - start) * 1000

        predicted = result["intent"]
        expected_norm = "unknown_intent" if expected == "unknown" else expected
        is_correct = int(predicted == expected_norm)

        predicted_intents.append(predicted)
        correct_flags.append(is_correct)
        elapsed_times_ms.append(elapsed_ms)

        mark = "correct" if is_correct else "WRONG"
        print(f'  [{mark}] "{utterance}" -> {predicted} (expected {expected}, {elapsed_ms:.1f} ms)')

    df["Predicted Intent"] = predicted_intents
    df["Correct"] = correct_flags
    df.to_excel(results_path, index=False)

    total_ms = sum(elapsed_times_ms)
    accuracy = sum(correct_flags) / len(correct_flags)

    print(f"\nResults written to {os.path.basename(results_path)}")
    print(f"Accuracy: {sum(correct_flags)}/{len(correct_flags)} ({accuracy:.1%})")
    print(f"Avg classification time: {total_ms / len(correct_flags):.1f} ms")
    print(f"Total classification time: {total_ms:.1f} ms")


def main():
    parser = argparse.ArgumentParser(description="Stage 3 Conversational State Store demo")
    parser.add_argument(
        "mode", choices=["call", "live", "test"],
        help="'call' to replay a sample transcript as a simulated live call, "
             "'live' to type turns yourself, 'test' to score intent_test_dataset.xlsx",
    )
    parser.add_argument(
        "samples", nargs="*",
        help="'call' mode only: specific sample file(s) under samples/ (default: all of them)",
    )
    args = parser.parse_args()

    warm_up()

    if args.mode == "call":
        run_calls(args.samples)
    elif args.mode == "live":
        interactive_loop()
    else:
        run_test()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
