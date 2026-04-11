# Flow Code

A visual AI coding assistant that bridges human intent and AI execution through an interactive codebase map.

## The Idea

When you ask an AI to fix something, one side is always guessing — you think in plain names ("the thing that handles checkout retries"), the model needs paths, symbols, and edit sites. Flow Code builds a maintained bridge between the two:

- **An interactive map** of your codebase with user-friendly names and descriptions, anchored to real file locations and symbol IDs
- **An AI pipeline** (investigate → plan → confirm → execute) where you review a plain-language plan before any code is touched
- **No code surfaces to you** — after a run, you see the map with amber badges on changed nodes and a plain-language summary

## How It Works

1. Select nodes on the map pointing at the area of concern
2. Describe what needs fixing in plain terms
3. The AI investigates the codebase, then presents a numbered plan
4. You confirm (or request a revision) before execution
5. Changes appear as highlighted nodes on the map

## Stack

| Layer | Tech |
|-------|------|
| UI | React + Vite + React Flow |
| API | FastAPI (Python) |
| Agent | [AgentAPI](https://github.com/coder/agentapi) wrapping Aider |
| Model | DeepSeek (via API) |
| Graph | RAW index (deterministic) + overlay (user-friendly layer) |

## Running Locally

### Prerequisites

- Python 3.12+, `uv`
- Node 18+
- [AgentAPI](https://github.com/coder/agentapi/releases) binary on PATH
- [Aider](https://aider.chat) (`pip install aider-chat`)
- DeepSeek API key

### Setup

```bash
cp .env.example .env
# Fill in DEEPSEEK_API_KEY (and optionally AGENT_MODEL)
```

### Start the API

```bash
BRAINSTORM_PUBLIC_DIR=poc-brainstorm-ui/public \
BRAINSTORM_GOLDEN_REPO=fixtures/golden-fastapi \
uv --project packages/raw-indexer run uvicorn raw_indexer.api:app --host 0.0.0.0 --port 8000
```

### Start the UI

```bash
cd poc-brainstorm-ui
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`.

### Dry-Run Mode (no AI required)

```bash
WORK_DRY_RUN=1 BRAINSTORM_PUBLIC_DIR=poc-brainstorm-ui/public \
uv --project packages/raw-indexer run uvicorn raw_indexer.api:app --port 8000
```

Simulates the full investigate → plan → execute flow with stub data.

### Tests

```bash
cd packages/raw-indexer
uv run pytest -v
```

## Project Structure

```
packages/raw-indexer/     # FastAPI backend + indexer
  src/raw_indexer/
    api.py                # All HTTP endpoints + agent pipeline
    index.py              # Codebase indexer (RAW format)
    overlay.py            # User-friendly label layer
poc-brainstorm-ui/        # React frontend
  src/
    App.tsx               # Main app + map
    BriefPanel.tsx        # Task input
    WorkingPanel.tsx      # Live pipeline progress
    DonePanel.tsx         # Results
fixtures/golden-fastapi/  # Example repo used for testing
docs/product-vision/      # Design goals and architecture notes
```

## Status

Early-stage POC. The core investigate → plan → confirm → execute loop works end-to-end. Active development.
