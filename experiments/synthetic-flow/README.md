# Synthetic Flow Experiment

Does an LLM predict a code flow that matches the actual call graph, given only
the code's semantics (names, docstrings, source)? If yes, the code "reads like
it runs" — readable. If no, divergences are surprises worth flagging.

## Files

- `test_codebase.py` — 8-function signup flow used as the subject
- `parse_codebase.py` — AST parser: functions + static call edges
- `build_actual_flow.py` — ground truth flow from the call graph
- `build_synthetic_flow.py` — LLM-predicted flow, walks by asking "what's the natural next step?"
- `compare.py` — renders both as ASCII trees + diffs edges

## Run

```sh
export DEEPSEEK_API_KEY=...      # required for synthetic
cd experiments/synthetic-flow
python build_actual_flow.py
python build_synthetic_flow.py
python compare.py
```

## What to look for

- **matching edges** — the LLM predicted what the code actually does
- **actual only** — real calls the LLM did NOT predict (code is doing something opaque)
- **synthetic only** — calls the LLM expected that don't exist (names/docstrings suggest a connection that isn't there)

## Knobs (in `build_synthetic_flow.py`)

- `CONFIDENCE_THRESHOLD = 0.55` — below this, edges are dropped
- `MAX_BRANCHES_PER_NODE = 2` — cap on how many candidates per step
- `MAX_DEPTH = 10` — how far to walk from the entry point
