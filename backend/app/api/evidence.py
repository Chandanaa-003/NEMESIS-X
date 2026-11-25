from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.user import User
from app.schemas.evidence import AnalysisEvidenceListResponse, EvidenceItemInfo

router = APIRouter(tags=["Evidence"])


def _to_evidence_info(item: Evidence, api_prefix: str) -> EvidenceItemInfo:
    meta = item.metadata_json or {}
    ev_type = (
        item.evidence_type
        if item.evidence_type in {"original_frame", "annotated_detection", "annotated_tracking"}
        else "original_frame"
    )
    return EvidenceItemInfo(
        id=item.id,
        event_id=item.event_id,
        analysis_id=item.analysis_id,
        frame_number=item.frame_number,
        timestamp_seconds=item.timestamp_seconds,
        evidence_type=ev_type,  # type: ignore[arg-type]
        image_url=f"{api_prefix}/evidence/{item.id}/image",
        description=item.description,
        event_title=str(meta.get("event_title", "Discovered Event")),
        event_category=str(meta.get("event_category", "other_activities")),
        event_severity=str(meta.get("event_severity", "low")),
        event_confidence=float(meta.get("event_confidence", 0.0)),
        why_flagged=str(meta.get("why_flagged", "")),
        involved_track_ids=[int(t) for t in meta.get("involved_track_ids", [])],
        detection_count=int(meta.get("detection_count", 0)),
        detection_summary=[str(s) for s in meta.get("detection_summary", [])],
        created_at=item.created_at,
    )


@router.get(
    "/analysis/{analysis_id}/evidence",
    response_model=AnalysisEvidenceListResponse,
    summary="List saved visual evidence artifacts for an owned analysis",
)
def list_analysis_evidence(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisEvidenceListResponse:
    """Return all saved evidence items for an owned analysis."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
        .first()
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )

    items = (
        db.query(Evidence)
        .filter(Evidence.analysis_id == analysis.id, Evidence.user_id == current_user.id)
        .order_by(Evidence.timestamp_seconds.asc(), Evidence.frame_number.asc())
        .all()
    )
    api_prefix = get_settings().api_v1_prefix
    return AnalysisEvidenceListResponse(
        analysis_id=analysis.id,
        total_evidence=len(items),
        evidence=[_to_evidence_info(item, api_prefix) for item in items],
    )


@router.get(
    "/events/{event_id}/evidence",
    response_model=AnalysisEvidenceListResponse,
    summary="List saved visual evidence artifacts for a specific owned event",
)
def list_event_evidence(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisEvidenceListResponse:
    """Return all saved evidence items for an owned event."""
    event = (
        db.query(Event)
        .join(Analysis, Event.analysis_id == Analysis.id)
        .filter(Event.id == event_id, Analysis.user_id == current_user.id)
        .first()
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    items = (
        db.query(Evidence)
        .filter(Evidence.event_id == event.id, Evidence.user_id == current_user.id)
        .order_by(Evidence.frame_number.asc(), Evidence.evidence_type.asc())
        .all()
    )
    api_prefix = get_settings().api_v1_prefix
    return AnalysisEvidenceListResponse(
        analysis_id=event.analysis_id,
        total_evidence=len(items),
        evidence=[_to_evidence_info(item, api_prefix) for item in items],
    )


@router.get(
    "/evidence/{evidence_id}/image",
    summary="Fetch a saved evidence JPEG securely for the owning user",
)
def get_evidence_image(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Validate ownership and stream an evidence JPEG strictly inside storage/evidence."""
    item = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence artifact not found.",
        )

    settings = get_settings()
    evidence_root = settings.resolved_evidence_dir.resolve()
    project_root = BACKEND_DIR.parent
    candidate = (project_root / item.file_path).resolve()

    try:
        candidate.relative_to(evidence_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid evidence file path.",
        ) from exc

    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence image file is missing on disk.",
        )

    return FileResponse(path=candidate, media_type="image/jpeg")
