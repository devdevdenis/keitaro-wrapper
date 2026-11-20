import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import campaigns, dictionaries, meta
from app.config import get_settings
from app.db import engine
from app.keitaro import (
    KeitaroAPIError,
    KeitaroError,
    KeitaroNotConfigured,
    KeitaroUnavailable,
    build_keitaro_client,
)
from app.services.campaigns import ServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.keitaro = await build_keitaro_client(get_settings())
    yield
    if app.state.keitaro is not None:
        await app.state.keitaro.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(meta.router)
    api.include_router(dictionaries.router)
    api.include_router(campaigns.router)
    app.include_router(api)

    @app.exception_handler(KeitaroError)
    async def keitaro_error_handler(_: Request, exc: KeitaroError) -> JSONResponse:
        if isinstance(exc, KeitaroNotConfigured | KeitaroUnavailable):
            code = 503
        elif isinstance(exc, KeitaroAPIError) and exc.status_code == 404:
            code = 404
        elif isinstance(exc, KeitaroAPIError) and exc.status_code in (400, 406, 422):
            code = 422
        else:
            code = 502
        return JSONResponse(
            status_code=code,
            content={
                "detail": exc.message,
                "source": "keitaro",
                "keitaro_status": exc.status_code,
                "errors": exc.details,
            },
        )

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    return app


app = create_app()
