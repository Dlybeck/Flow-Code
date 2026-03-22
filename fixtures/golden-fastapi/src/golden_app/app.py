"""FastAPI entry: routes only; logic lives in `core`."""

from fastapi import FastAPI

from golden_app.core import greeting_for


def create_app() -> FastAPI:
    app = FastAPI(title="Golden Fixture API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/greet/{name}")
    def greet(name: str) -> dict[str, str]:
        return {"message": greeting_for(name)}

    return app


app = create_app()
