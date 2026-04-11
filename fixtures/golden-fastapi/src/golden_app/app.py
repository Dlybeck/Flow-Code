"""FastAPI entry: routes only; logic lives in `core`."""

from fastapi import FastAPI

from golden_app.core import greeting_for, goodbye_for


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with all routes."""
    app = FastAPI(title="Golden Fixture API")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Health check endpoint to verify API is running."""
        return {"status": "ok"}

    @app.get("/greet/{name}")
    @app.get("/greet/")
    def greet(name: str | None = None) -> dict[str, str]:
        """Greet endpoint that returns a personalized greeting message."""
        return {"message": greeting_for(name)}

    @app.get("/goodbye/{name}")
    @app.get("/goodbye/")
    def goodbye(name: str | None = None) -> dict[str, str]:
        """Goodbye endpoint that returns a personalized farewell message."""
        return {"message": goodbye_for(name)}

    return app


app = create_app()
