from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings


def create_application() -> FastAPI:
    """Create and configure the NEMESIS-X FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)

    @application.get("/", tags=["Root"], summary="Application info")
    async def root() -> dict[str, str]:
        """Return basic NEMESIS-X API metadata."""
        return {
            "application": settings.app_name,
            "description": settings.app_description,
            "version": settings.app_version,
            "health": f"{settings.api_v1_prefix}/health",
            "docs": "/docs",
        }

    return application


app = create_application()
