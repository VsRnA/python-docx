from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from document_service.infrastructure.config.settings import get_settings
from document_service.presentation.api.v1.router import api_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-User-ID"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
