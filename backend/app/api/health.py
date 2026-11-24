import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import SessionDep

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(session: SessionDep):
    try:
        async with asyncio.timeout(3):
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # any failure here means the app can't serve requests
        logger.warning("health check failed", extra={"error": repr(exc)})
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "ok"}
