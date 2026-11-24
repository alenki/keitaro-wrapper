from collections.abc import Sequence
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import __version__
from app.api import campaigns, catalog, health
from app.config import Settings, get_settings
from app.db import create_engine
from app.errors import register_error_handlers
from app.keitaro.client import KeitaroClient
from app.log import setup_logging
from app.middleware import RequestContextMiddleware
from app.services.catalog import Catalog
from app.services.editor import Editor


def create_app(
    settings: Settings | None = None,
    *,
    keitaro_transport: httpx.AsyncBaseTransport | None = None,
    keitaro_retry_delays: Sequence[float] = (0.3, 0.9),
) -> FastAPI:
    """Build the app. Tests pass their own settings and a fake Keitaro transport."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        keitaro = KeitaroClient(
            settings.keitaro_url,
            settings.keitaro_api_key.get_secret_value(),
            timeout=settings.keitaro_timeout_seconds,
            transport=keitaro_transport,
            retry_delays=keitaro_retry_delays,
        )
        app.state.session_factory = session_factory
        app.state.keitaro = keitaro
        catalog = Catalog(keitaro, session_factory, settings.catalog_ttl_seconds)
        app.state.catalog = catalog
        app.state.editor = Editor(keitaro, catalog)
        try:
            yield
        finally:
            await keitaro.aclose()
            await engine.dispose()

    app = FastAPI(
        title="Keitaro wrapper",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(catalog.router, prefix="/api")
    app.include_router(campaigns.router, prefix="/api")
    return app
