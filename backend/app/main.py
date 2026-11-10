"""HTTP entry point. Code analysis will live in a separate module."""

from fastapi import FastAPI

app = FastAPI(
    title="Explain This Codebase",
    description="Explore Python project structure using static analysis.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Confirm that the API process can answer requests."""
    return {"status": "ok"}
