from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.monitoring import (
    IntelligenceAnalyticsResponse,
    MonitoringHistoryResponse,
    UnifiedSessionDetailResponse,
)
from app.services.monitoring_service import (
    get_intelligence_analytics,
    get_monitoring_history,
    get_unified_session_detail,
)

router = APIRouter(prefix="/monitoring", tags=["Monitoring & Analytics"])


@router.get(
    "/history",
    response_model=MonitoringHistoryResponse,
    summary="Get unified monitoring history for recorded video analyses and live webcam monitoring",
)
def list_monitoring_history(
    session_type: str = Query(default="all", description="Filter by session type: all, recorded, live"),
    status: str | None = Query(default=None, description="Filter by session status"),
    priority: str | None = Query(default=None, description="Filter by event priority: high, medium, low"),
    search: str | None = Query(default=None, description="Search by session name or ID"),
    date_from: datetime | None = Query(default=None, description="Filter sessions starting on or after"),
    date_to: datetime | None = Query(default=None, description="Filter sessions starting on or before"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitoringHistoryResponse:
    """Return filtered and paginated sessions across recorded analysis and live webcam monitoring."""
    return get_monitoring_history(
        user_id=current_user.id,
        session_type=session_type,
        status_filter=status,
        priority_filter=priority,
        search=search,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.get(
    "/analytics",
    response_model=IntelligenceAnalyticsResponse,
    summary="Get real aggregated intelligence analytics across user sessions, detections, tracks, and events",
)
def get_monitoring_intelligence_analytics(
    date_from: datetime | None = Query(default=None, description="Filter metrics on or after"),
    date_to: datetime | None = Query(default=None, description="Filter metrics on or before"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntelligenceAnalyticsResponse:
    """Compute and return truthful aggregated intelligence metrics based strictly on database records."""
    return get_intelligence_analytics(
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
        db=db,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=UnifiedSessionDetailResponse,
    summary="Get full unified session details with detection stats, tracks, events, evidence, and AI assistant breakdown",
)
def get_session_details(
    session_id: str,
    session_type: str | None = Query(default=None, description="Optional hint: recorded or live"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnifiedSessionDetailResponse:
    """Return comprehensive session overview, event timeline, tracks, evidence, and report link."""
    settings = get_settings()
    return get_unified_session_detail(
        session_id=session_id,
        user_id=current_user.id,
        session_type=session_type,
        db=db,
        api_prefix=settings.api_v1_prefix,
    )
