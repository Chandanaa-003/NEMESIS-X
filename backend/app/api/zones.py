from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.live_session import LiveEvent, LiveSession
from app.models.user import User
from app.models.video import Video
from app.models.zone import Zone
from app.schemas.zone import (
    ZoneActivitySummary,
    ZoneCreateRequest,
    ZoneEventResponse,
    ZoneResponse,
    ZoneUpdateRequest,
)
from app.services.zone_engine import summarize_zone_events

router = APIRouter(prefix="/zones", tags=["Smart Zones"])


def _owned_video(video_id: str, user_id: int, db: Session) -> Video:
    video = db.query(Video).filter(Video.id == video_id, Video.user_id == user_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return video


def _owned_live_session(session_id: str, user_id: int, db: Session) -> LiveSession:
    session = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == user_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Live monitoring session not found.")
    return session


def _owned_analysis(analysis_id: str, user_id: int, db: Session) -> Analysis:
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    return analysis


def _zone_event_info(
    *,
    event: Event | LiveEvent,
    source_id: str,
    api_prefix: str,
    live: bool,
) -> ZoneEventResponse | None:
    payload: dict[str, Any] = event.explanation_payload or {}
    zone_id = payload.get("zone_id")
    if not zone_id:
        return None
    evidence_reference = (
        f"{api_prefix}/live/{source_id}/events/{event.id}/snapshot"
        if live and getattr(event, "snapshot_path", None)
        else f"{api_prefix}/events/{event.id}/evidence"
        if not live
        else None
    )
    return ZoneEventResponse(
        id=event.id,
        source_id=source_id,
        event_type=event.event_type,
        zone_id=str(zone_id),
        zone_name=str(payload.get("zone_name", "Zone")),
        zone_type=payload.get("zone_type", "monitoring"),
        start_timestamp=event.start_timestamp,
        end_timestamp=event.end_timestamp,
        duration_seconds=round(
            max(
                0.0,
                float(payload.get("duration_seconds", event.end_timestamp - event.start_timestamp)),
            ),
            3,
        ),
        involved_track_ids=[int(track_id) for track_id in (event.involved_track_ids or [])],
        confidence=event.confidence,
        severity=event.severity,
        description=event.description,
        evidence_frame_ids=[int(frame_id) for frame_id in (event.evidence_frame_ids or [])]
        if isinstance(event, Event)
        else [int(event.frame_index)],
        evidence_reference=evidence_reference,
        voice_alerts_enabled=bool(payload.get("voice_alerts_enabled", True)),
        created_at=event.created_at,
    )


def _event_summary_payload(events: Sequence[ZoneEventResponse]) -> list[dict[str, Any]]:
    return [
        {
            "event_type": event.event_type,
            "zone_id": event.zone_id,
            "zone_name": event.zone_name,
            "end_timestamp": event.end_timestamp,
            "involved_track_ids": event.involved_track_ids,
        }
        for event in events
    ]


@router.get("", response_model=list[ZoneResponse], summary="List owned video and live-session zones")
def list_zones(
    video_id: str | None = Query(default=None),
    live_session_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ZoneResponse]:
    if video_id is not None and live_session_id is not None:
        raise HTTPException(status_code=400, detail="Choose a video or live session scope, not both.")
    query = db.query(Zone).filter(Zone.user_id == current_user.id)
    if video_id is not None:
        _owned_video(video_id, current_user.id, db)
        query = query.filter(Zone.video_id == video_id)
    elif live_session_id is not None:
        _owned_live_session(live_session_id, current_user.id, db)
        query = query.filter(Zone.live_session_id == live_session_id)
    return [
        ZoneResponse.model_validate(zone)
        for zone in query.order_by(Zone.created_at.asc()).all()
    ]


@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a normalized polygon zone",
)
def create_zone(
    payload: ZoneCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZoneResponse:
    if payload.video_id is not None:
        _owned_video(payload.video_id, current_user.id, db)
    elif payload.live_session_id is not None:
        _owned_live_session(payload.live_session_id, current_user.id, db)
    zone = Zone(
        user_id=current_user.id,
        video_id=payload.video_id,
        live_session_id=payload.live_session_id,
        name=payload.name.strip(),
        zone_type=payload.zone_type,
        color=payload.color.upper(),
        polygon=payload.polygon,
        settings=payload.settings.model_dump(),
    )
    try:
        db.add(zone)
        db.commit()
        db.refresh(zone)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while creating zone.") from exc
    return ZoneResponse.model_validate(zone)


@router.patch("/{zone_id}", response_model=ZoneResponse, summary="Edit a polygon zone")
def update_zone(
    zone_id: str,
    payload: ZoneUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZoneResponse:
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id, Zone.user_id == current_user.id)
        .first()
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "settings" and value is not None:
            setattr(zone, key, payload.settings.model_dump())
        elif value is not None:
            setattr(zone, key, value)
    if zone.name:
        zone.name = zone.name.strip()
    if zone.color:
        zone.color = zone.color.upper()
    try:
        db.commit()
        db.refresh(zone)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while updating zone.") from exc
    return ZoneResponse.model_validate(zone)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an owned zone")
def delete_zone(
    zone_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id, Zone.user_id == current_user.id)
        .first()
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found.")
    try:
        db.delete(zone)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while deleting zone.") from exc


@router.get(
    "/analysis/{analysis_id}/events",
    response_model=list[ZoneEventResponse],
    summary="List confirmed zone events for an owned video analysis",
)
def list_analysis_zone_events(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ZoneEventResponse]:
    analysis = _owned_analysis(analysis_id, current_user.id, db)
    rows = (
        db.query(Event)
        .filter(Event.analysis_id == analysis.id)
        .order_by(Event.start_timestamp.asc())
        .all()
    )
    settings = get_settings()
    return [
        event_info
        for row in rows
        if (
            event_info := _zone_event_info(
                event=row,
                source_id=analysis.id,
                api_prefix=settings.api_v1_prefix,
                live=False,
            )
        )
        is not None
    ]


@router.get(
    "/live/{session_id}/events",
    response_model=list[ZoneEventResponse],
    summary="List confirmed zone events for an owned live session",
)
def list_live_zone_events(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ZoneEventResponse]:
    _owned_live_session(session_id, current_user.id, db)
    rows = (
        db.query(LiveEvent)
        .filter(LiveEvent.session_id == session_id, LiveEvent.user_id == current_user.id)
        .order_by(LiveEvent.start_timestamp.asc())
        .all()
    )
    settings = get_settings()
    return [
        event_info
        for row in rows
        if (
            event_info := _zone_event_info(
                event=row,
                source_id=session_id,
                api_prefix=settings.api_v1_prefix,
                live=True,
            )
        )
        is not None
    ]


@router.get(
    "/analysis/{analysis_id}/activity",
    response_model=ZoneActivitySummary,
    summary="Summarize zone activity for an owned video analysis",
)
def get_analysis_zone_activity(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZoneActivitySummary:
    events = list_analysis_zone_events(analysis_id, current_user, db)
    return ZoneActivitySummary.model_validate(
        summarize_zone_events(
            source_id=analysis_id,
            events=_event_summary_payload(events),
        )
    )


@router.get(
    "/live/{session_id}/activity",
    response_model=ZoneActivitySummary,
    summary="Summarize zone activity for an owned live session",
)
def get_live_zone_activity(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZoneActivitySummary:
    events = list_live_zone_events(session_id, current_user, db)
    return ZoneActivitySummary.model_validate(
        summarize_zone_events(
            source_id=session_id,
            events=_event_summary_payload(events),
        )
    )


@router.get(
    "/video/{video_id}/activity",
    response_model=ZoneActivitySummary,
    summary="Summarize saved zone events across a video's analyses",
)
def get_video_zone_activity(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZoneActivitySummary:
    video = _owned_video(video_id, current_user.id, db)
    analyses = db.query(Analysis).filter(Analysis.video_id == video.id).all()
    analysis_ids = [analysis.id for analysis in analyses]
    rows = (
        db.query(Event)
        .filter(Event.analysis_id.in_(analysis_ids))
        .order_by(Event.start_timestamp.asc())
        .all()
        if analysis_ids
        else []
    )
    events = [
        event_info
        for row in rows
        if (
            event_info := _zone_event_info(
                event=row,
                source_id=row.analysis_id,
                api_prefix=get_settings().api_v1_prefix,
                live=False,
            )
        )
        is not None
    ]
    return ZoneActivitySummary.model_validate(
        summarize_zone_events(
            source_id=video.id,
            events=_event_summary_payload(events),
        )
    )
