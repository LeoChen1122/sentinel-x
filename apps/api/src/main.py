"""Sentinel-X FastAPI entry (W7)."""

from __future__ import annotations

from fastapi import FastAPI

from routes.inspect import router as inspect_router
from routes.webhooks import router as webhooks_router

app = FastAPI(
    title="Sentinel-X API",
    description="Alert webhook and inspect trigger (W7)",
    version="0.1.0",
)

app.include_router(inspect_router)
app.include_router(webhooks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
