"""Health endpoint for service monitoring."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a minimal response confirming the API is running."""
    return {"status": "ok", "service": settings.app_name}
