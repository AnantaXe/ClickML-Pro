"""Health & readiness endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "service": "clickml-pro", "version": "0.1.0"}


@router.get("/ready", tags=["Health"])
async def ready() -> dict:
    return {"ready": True}
