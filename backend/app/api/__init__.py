from fastapi import APIRouter

from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.videos import router as videos_router
from app.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(videos_router)
api_router.include_router(analysis_router)
api_router.include_router(events_router)
api_router.include_router(evidence_router)
api_router.include_router(reports_router)
