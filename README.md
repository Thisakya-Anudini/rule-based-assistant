# Rule-Based Assistant

## Project layout

- `rule_based_assistant/` contains the application, rule engine, and demo code.
- `samples/` contains sample customer conversations.
- `tests/` contains the automated tests.
- `requirements.txt` lists the Python dependencies.

## Install

From the repository root, run:

```powershell
python -m pip install -r requirements.txt
```

## Test

```powershell
python -m pytest tests -q
```

## Try a sample conversation

```powershell
python -m rule_based_assistant.examples.demo call "Medium (1).txt"
```

For interactive turns, use `live` instead of `call`.

## Optional Laya intent classification

The assistant uses its deterministic rules by default. To optionally compare each
message with Laya, install the extra dependencies and enable the router:

```powershell
python -m pip install -r requirements-laya.txt
$env:LAYA_ROUTER_ENABLED = "true"
python -m uvicorn rule_based_assistant.server:app --reload
```

The integration code is included in this repository in
`rule_based_assistant/laya_adapter.py`. The optional `laya==0.3.28` dependency is
installed from Python's package index; you do not need to copy or commit the
separate Laya source repository. The base `requirements.txt` does not install
Laya, so the assistant continues to run with rules alone unless you install
`requirements-laya.txt` and enable the router.

On first use, Laya downloads its model checkpoint. Set
`LAYA_CONFIDENCE_THRESHOLD` to a value from `0` to `1` to change its acceptance
threshold; the default is `0.85`.

The browser demo at `/demo` also has an **Enable Laya / Disable Laya** button.
It changes the setting for the running server process and resets to the
environment setting (or disabled by default) when the server restarts.

When enabled, Laya and the rule engine classify the same message. The rule engine
continues to win if it returns a known intent, including disagreements and
clarification/multiple-intent decisions. A valid Laya intent is used only when
the rule engine returns `unknown_intent` and Laya's `answer_confidence` meets the
threshold. Laya failures or unsupported labels leave the rule result unchanged.
The comparison is recorded in the existing `logs/turns.jsonl` turn record under
`raw_trace.model_comparison`. The rule-based behavior is unchanged when Laya is
disabled (the default).

## Run the API and browser demo

```powershell
python -m uvicorn rule_based_assistant.server:app --reload
```

Open <http://127.0.0.1:8000/demo> for the browser demo or <http://127.0.0.1:8000/docs> for the API documentation.