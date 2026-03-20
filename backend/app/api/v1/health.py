from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check():
    """Basic health check — no auth required."""
    return {"status": "ok", "version": "1.0"}
