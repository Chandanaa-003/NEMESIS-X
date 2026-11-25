import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.identity import EntityIdentity, IdentityTrackAssociation
from app.models.live_session import LiveEvent, LiveSession
from app.models.user import User
from app.schemas.identity import (
    EntityIdentityDetail,
    EntityIdentitySummary,
    IdentityCorrectionRequest,
    IdentityCountsResponse,
    IdentityEntityType,
    IdentityRelatedEventInfo,
    IdentitySearchResponse,
    IdentitySourceType,
    IdentityTrackAppearanceInfo,
)
from app.services.identity_engine import correct_track_identity
from app.services.track_explorer import format_track_code

router = APIRouter(prefix="/identities", tags=["Persistent Identities"])
SAFE_FRAME_FILENAME_RE = re.compile(r"^frame_\d{4}\.jpg$")
SAFE_LIVE_EVIDENCE_FILENAME_RE = re.compile(r"^identity_t\d+_f\d+\.jpg$")
TRACK_CODE_RE = re.compile(r"^T(\d+)$", re.IGNORECASE)
IDENTITY_CODE_RE = re.compile(r"^[PO]\d+$", re.IGNORECASE)


def _require_owned_source(
    db: Session,
    *,
    source_type: IdentitySourceType,
    source_id: str,
    user_id: int,
) -> None:
    if source_type == "analysis":
        source = (
            db.query(Analysis)
            .filter(Analysis.id == source_id, Analysis.user_id == user_id)
            .first()
        )
    else:
        source = (
            db.query(LiveSession)
            .filter(LiveSession.id == source_id, LiveSession.user_id == user_id)
            .first()
        )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")


def _get_owned_identity(db: Session, identity_id: str, user_id: int) -> EntityIdentity:
    identity = (
        db.query(EntityIdentity)
        .filter(EntityIdentity.id == identity_id, EntityIdentity.user_id == user_id)
        .first()
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found.")
    _require_owned_source(
        db,
        source_type=identity.source_type,  # type: ignore[arg-type]
        source_id=identity.source_id,
        user_id=user_id,
    )
    return identity


def _all_source_events(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    user_id: int,
) -> list[Event | LiveEvent]:
    if source_type == "analysis":
        return (
            db.query(Event)
            .filter(Event.analysis_id == source_id)
            .order_by(Event.start_timestamp.asc(), Event.id.asc())
            .limit(2000)
            .all()
        )
    return (
        db.query(LiveEvent)
        .filter(
            LiveEvent.session_id == source_id,
            LiveEvent.user_id == user_id,
        )
        .order_by(LiveEvent.timestamp_seconds.asc(), LiveEvent.id.asc())
        .limit(2000)
        .all()
    )


def _event_track_ids(event: Event | LiveEvent) -> set[int]:
    result: set[int] = set()
    for track_id in event.involved_track_ids or []:
        if isinstance(track_id, int) or (isinstance(track_id, str) and track_id.isdigit()):
            result.add(int(track_id))
    return result


def _matching_events(
    events: list[Event | LiveEvent],
    track_ids: set[int],
) -> list[Event | LiveEvent]:
    if not track_ids:
        return []
    return [
        row
        for row in events
        if track_ids.intersection(_event_track_ids(row))
    ]


def _event_info(
    event: Event | LiveEvent,
    track_ids: set[int],
) -> IdentityRelatedEventInfo:
    if isinstance(event, Event):
        timestamp = event.start_timestamp
        event_type = event.event_type
        category = event.category
        title = event.title
        confidence = event.confidence
        severity = event.severity
    else:
        timestamp = event.timestamp_seconds
        event_type = event.event_type
        category = event.category
        title = event.title
        confidence = event.confidence
        severity = event.severity
    matched_ids = _event_track_ids(event).intersection(track_ids)
    return IdentityRelatedEventInfo(
        id=event.id,
        event_type=event_type,
        category=category,
        title=title,
        timestamp_seconds=timestamp,
        confidence=confidence,
        severity=severity,
        track_codes=[format_track_code(track_id) for track_id in sorted(matched_ids)],
    )


def _association_rows(
    db: Session,
    identity: EntityIdentity,
) -> list[IdentityTrackAssociation]:
    return (
        db.query(IdentityTrackAssociation)
        .filter(IdentityTrackAssociation.identity_id == identity.id)
        .order_by(
            IdentityTrackAssociation.first_seen_timestamp.asc(),
            IdentityTrackAssociation.track_id.asc(),
        )
        .all()
    )


def _evidence_url(api_prefix: str, identity: EntityIdentity, track_id: int) -> str:
    return (
        f"{api_prefix}/identities/{identity.id}/tracks/{track_id}/evidence"
    )


def _track_info(
    association: IdentityTrackAssociation,
    identity: EntityIdentity,
    api_prefix: str,
) -> IdentityTrackAppearanceInfo:
    return IdentityTrackAppearanceInfo(
        track_id=association.track_id,
        track_code=format_track_code(association.track_id),
        category=association.category,
        first_seen_timestamp=association.first_seen_timestamp,
        last_seen_timestamp=association.last_seen_timestamp,
        detection_count=association.detection_count,
        match_confidence=association.match_confidence,
        match_status=association.match_status,  # type: ignore[arg-type]
        matching_explanation=association.matching_explanation,
        unresolved_candidate_code=association.unresolved_candidate_code,
        evidence_url=(
            _evidence_url(api_prefix, identity, association.track_id)
            if association.evidence_reference
            else None
        ),
        manually_corrected=association.manually_corrected,
        correction_note=association.correction_note,
    )


def _summary(
    db: Session,
    identity: EntityIdentity,
    api_prefix: str,
    *,
    related_events: list[Event | LiveEvent] | None = None,
) -> EntityIdentitySummary:
    associations = _association_rows(db, identity)
    track_ids = {association.track_id for association in associations}
    events = (
        related_events
        if related_events is not None
        else _matching_events(
            _all_source_events(
                db,
                source_type=identity.source_type,
                source_id=identity.source_id,
                user_id=identity.user_id,
            ),
            track_ids,
        )
    )
    merged_into = (
        db.query(EntityIdentity)
        .filter(EntityIdentity.id == identity.merged_into_identity_id)
        .first()
        if identity.merged_into_identity_id
        else None
    )
    return EntityIdentitySummary(
        id=identity.id,
        identity_code=identity.identity_code,
        source_type=identity.source_type,  # type: ignore[arg-type]
        source_id=identity.source_id,
        entity_type=identity.entity_type,  # type: ignore[arg-type]
        category=identity.category,
        first_seen_timestamp=identity.first_seen_timestamp,
        last_seen_timestamp=identity.last_seen_timestamp,
        appearance_count=identity.appearance_count,
        matching_confidence=identity.matching_confidence,
        status=identity.status,  # type: ignore[arg-type]
        matching_explanation=identity.matching_explanation,
        associated_track_ids=[item.track_id for item in associations],
        associated_track_codes=[
            format_track_code(item.track_id) for item in associations
        ],
        evidence_urls=[
            _evidence_url(api_prefix, identity, item.track_id)
            for item in associations
            if item.evidence_reference
        ],
        related_event_count=len(events),
        merged_into_code=merged_into.identity_code if merged_into else None,
    )


def _detail(
    db: Session,
    identity: EntityIdentity,
    api_prefix: str,
) -> EntityIdentityDetail:
    associations = _association_rows(db, identity)
    track_ids = {item.track_id for item in associations}
    events = _matching_events(
        _all_source_events(
            db,
            source_type=identity.source_type,
            source_id=identity.source_id,
            user_id=identity.user_id,
        ),
        track_ids,
    )
    summary = _summary(db, identity, api_prefix, related_events=events)
    return EntityIdentityDetail(
        **summary.model_dump(),
        track_appearances=[
            _track_info(item, identity, api_prefix) for item in associations
        ],
        related_events=[_event_info(event, track_ids) for event in events],
    )


@router.get(
    "",
    response_model=IdentitySearchResponse,
    summary="Search anonymous identities within one owned video or live session",
)
def search_identities(
    source_type: IdentitySourceType,
    source_id: str = Query(min_length=1, max_length=36),
    entity_type: IdentityEntityType | None = None,
    identity_code: str | None = Query(default=None, max_length=16),
    track_id: int | None = Query(default=None, ge=0),
    query: str | None = Query(default=None, max_length=100),
    min_appearances: int = Query(default=1, ge=1),
    first_seen_from: float | None = Query(default=None, ge=0),
    first_seen_to: float | None = Query(default=None, ge=0),
    last_seen_from: float | None = Query(default=None, ge=0),
    last_seen_to: float | None = Query(default=None, ge=0),
    event_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentitySearchResponse:
    """Return unique entities only for the selected source; IDs never cross sources."""
    _require_owned_source(
        db,
        source_type=source_type,
        source_id=source_id,
        user_id=current_user.id,
    )
    statement = db.query(EntityIdentity).filter(
        EntityIdentity.user_id == current_user.id,
        EntityIdentity.source_type == source_type,
        EntityIdentity.source_id == source_id,
        EntityIdentity.appearance_count >= min_appearances,
        EntityIdentity.merged_into_identity_id.is_(None),
    )
    if entity_type:
        statement = statement.filter(EntityIdentity.entity_type == entity_type)
    if identity_code:
        statement = statement.filter(
            EntityIdentity.identity_code.ilike(identity_code.strip())
        )
    if first_seen_from is not None:
        statement = statement.filter(EntityIdentity.first_seen_timestamp >= first_seen_from)
    if first_seen_to is not None:
        statement = statement.filter(EntityIdentity.first_seen_timestamp <= first_seen_to)
    if last_seen_from is not None:
        statement = statement.filter(EntityIdentity.last_seen_timestamp >= last_seen_from)
    if last_seen_to is not None:
        statement = statement.filter(EntityIdentity.last_seen_timestamp <= last_seen_to)
    if track_id is not None:
        statement = statement.join(
            IdentityTrackAssociation,
            IdentityTrackAssociation.identity_id == EntityIdentity.id,
        ).filter(IdentityTrackAssociation.track_id == track_id)
    if query:
        term = query.strip()
        track_match = TRACK_CODE_RE.fullmatch(term)
        if track_match:
            statement = statement.join(
                IdentityTrackAssociation,
                IdentityTrackAssociation.identity_id == EntityIdentity.id,
            ).filter(IdentityTrackAssociation.track_id == int(track_match.group(1)))
        elif IDENTITY_CODE_RE.fullmatch(term):
            statement = statement.filter(EntityIdentity.identity_code.ilike(term))
        else:
            statement = statement.filter(EntityIdentity.category.ilike(f"%{term}%"))

    identities = (
        statement.order_by(
            EntityIdentity.first_seen_timestamp.asc(),
            EntityIdentity.identity_code.asc(),
        )
        .all()
    )
    source_events = _all_source_events(
        db,
        source_type=source_type,
        source_id=source_id,
        user_id=current_user.id,
    )
    events_by_identity: dict[str, list[Event | LiveEvent]] = {}
    for identity in identities:
        track_ids = {
            association.track_id
            for association in _association_rows(db, identity)
        }
        related_events = _matching_events(source_events, track_ids)
        events_by_identity[identity.id] = related_events

    if event_type:
        identities = [
            identity
            for identity in identities
            if any(event.event_type == event_type for event in events_by_identity[identity.id])
        ]
    total = len(identities)
    page = identities[offset : offset + limit]
    api_prefix = get_settings().api_v1_prefix
    return IdentitySearchResponse(
        items=[
            _summary(
                db,
                identity,
                api_prefix,
                related_events=events_by_identity[identity.id],
            )
            for identity in page
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/counts",
    response_model=IdentityCountsResponse,
    summary="Count unique people and objects in one owned source",
)
def get_identity_counts(
    source_type: IdentitySourceType,
    source_id: str = Query(min_length=1, max_length=36),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityCountsResponse:
    _require_owned_source(
        db,
        source_type=source_type,
        source_id=source_id,
        user_id=current_user.id,
    )
    rows = (
        db.query(EntityIdentity.entity_type, func.count(EntityIdentity.id))
        .filter(
            EntityIdentity.user_id == current_user.id,
            EntityIdentity.source_type == source_type,
            EntityIdentity.source_id == source_id,
            EntityIdentity.appearance_count > 0,
            EntityIdentity.merged_into_identity_id.is_(None),
        )
        .group_by(EntityIdentity.entity_type)
        .all()
    )
    counts = {str(entity_type): int(count) for entity_type, count in rows}
    status_counts = (
        db.query(EntityIdentity.status, func.count(EntityIdentity.id))
        .filter(
            EntityIdentity.user_id == current_user.id,
            EntityIdentity.source_type == source_type,
            EntityIdentity.source_id == source_id,
            EntityIdentity.appearance_count > 0,
            EntityIdentity.merged_into_identity_id.is_(None),
        )
        .group_by(EntityIdentity.status)
        .all()
    )
    statuses = {str(match_status): int(count) for match_status, count in status_counts}
    return IdentityCountsResponse(
        unique_people=counts.get("person", 0),
        unique_objects=counts.get("object", 0),
        confirmed=statuses.get("confirmed", 0),
        probable=statuses.get("probable", 0),
        unknown=statuses.get("unknown", 0),
    )


@router.get(
    "/{identity_id}",
    response_model=EntityIdentityDetail,
    summary="Get one source-scoped identity, its track fragments, events, and evidence",
)
def get_identity(
    identity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityIdentityDetail:
    identity = _get_owned_identity(db, identity_id, current_user.id)
    return _detail(db, identity, get_settings().api_v1_prefix)


@router.patch(
    "/{identity_id}/tracks/{track_id}",
    response_model=EntityIdentityDetail,
    summary="Manually correct a track-to-identity association",
)
def correct_identity_track(
    identity_id: str,
    track_id: int,
    payload: IdentityCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityIdentityDetail:
    identity = _get_owned_identity(db, identity_id, current_user.id)
    if identity.appearance_count == 0:
        raise HTTPException(status_code=409, detail="Merged identities cannot be edited.")
    association = (
        db.query(IdentityTrackAssociation)
        .filter(
            IdentityTrackAssociation.identity_id == identity.id,
            IdentityTrackAssociation.source_type == identity.source_type,
            IdentityTrackAssociation.source_id == identity.source_id,
            IdentityTrackAssociation.track_id == track_id,
        )
        .first()
    )
    if association is None:
        raise HTTPException(status_code=404, detail="Track association not found.")
    if (payload.target_identity_id is not None) == payload.create_new_identity:
        raise HTTPException(
            status_code=422,
            detail="Provide either target_identity_id or create_new_identity=true.",
        )
    target_identity = None
    if payload.target_identity_id:
        target_identity = (
            db.query(EntityIdentity)
            .filter(
                EntityIdentity.id == payload.target_identity_id,
                EntityIdentity.user_id == current_user.id,
                EntityIdentity.appearance_count > 0,
                EntityIdentity.merged_into_identity_id.is_(None),
            )
            .first()
        )
        if target_identity is None:
            raise HTTPException(status_code=404, detail="Target identity not found.")
    try:
        corrected = correct_track_identity(
            db,
            identity=identity,
            association=association,
            user_id=current_user.id,
            target_identity=target_identity,
            create_new_identity=payload.create_new_identity,
            correction_note=payload.correction_note,
        )
        db.commit()
        db.refresh(corrected)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _detail(db, corrected, get_settings().api_v1_prefix)


@router.get(
    "/{identity_id}/tracks/{track_id}/evidence",
    summary="Fetch an existing frame or stored live appearance crop",
)
def get_identity_evidence(
    identity_id: str,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    identity = _get_owned_identity(db, identity_id, current_user.id)
    association = (
        db.query(IdentityTrackAssociation)
        .filter(
            IdentityTrackAssociation.identity_id == identity.id,
            IdentityTrackAssociation.source_type == identity.source_type,
            IdentityTrackAssociation.source_id == identity.source_id,
            IdentityTrackAssociation.track_id == track_id,
        )
        .first()
    )
    if association is None or not association.evidence_reference:
        raise HTTPException(status_code=404, detail="Identity evidence not found.")

    settings = get_settings()
    if identity.source_type == "analysis":
        filename = association.evidence_reference
        if not SAFE_FRAME_FILENAME_RE.fullmatch(filename):
            raise HTTPException(status_code=404, detail="Identity evidence not found.")
        frame_root = (settings.resolved_processed_dir / identity.source_id / "frames").resolve()
        target_path = (frame_root / filename).resolve()
        if target_path.parent != frame_root:
            raise HTTPException(status_code=404, detail="Identity evidence not found.")
    else:
        filename = association.evidence_reference
        if not SAFE_LIVE_EVIDENCE_FILENAME_RE.fullmatch(filename):
            raise HTTPException(status_code=404, detail="Identity evidence not found.")
        live_root = settings.resolved_live_dir.resolve()
        session_dir = (live_root / identity.source_id).resolve()
        evidence_dir = (session_dir / "identity-evidence").resolve()
        target_path = (evidence_dir / filename).resolve()
        if (
            session_dir.parent != live_root
            or evidence_dir.parent != session_dir
            or target_path.parent != evidence_dir
        ):
            raise HTTPException(status_code=404, detail="Identity evidence not found.")
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail="Identity evidence file missing.")
    return FileResponse(path=target_path, media_type="image/jpeg")
