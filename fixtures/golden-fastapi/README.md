# golden-fastapi

Minimal **FastAPI** package under `src/` layout with **pytest**. Used as the default fixture for [`packages/flowcode`](../../packages/flowcode).

```bash
cd fixtures/golden-fastapi
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn golden_app.app:app --reload   # optional manual run
```
