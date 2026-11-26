import json
import os
from pathlib import Path
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.event import Event
from app.models.identity import EntityIdentity, IdentityObservation
from app.models.live_session import LiveEvent, LiveSession
from app.models.user import User
from app.schemas.identity import (
    EntityIdentityResponse,
    IdentityCorrectionRequest,
    IdentityCorrectionResponse,
    IdentityCountsResponse,
    IdentityEntityType,
    IdentityLegacyCorrectionRequest,
    IdentityObservationResponse,
    IdentityRelatedEventResponse,
    IdentitySearchResponse,
    IdentitySourceType,
    IdentityStatus,
    IdentityTrackAppearanceCompatResponse,
)
from app.services.identity_engine import (
    aggregate_signatures,
    get_identity_evidence_path,
)
from app.services.live_monitor import refresh_live_identity_matcher

router = APIRouter(prefix="/identities", tags=["Persistent Identities"])


def _owned_source(
    source_type: IdentitySourceType, source_id: str, user_id: int, db: Session
) -> Analysis | LiveSession:
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
        raise HTTPException(status_code=404, detail="Identity source not found.")
    return source


def _identity_by_id(identity_id: str, user_id: int, db: Session) -> EntityIdentity:
    identity = (
        db.query(EntityIdentity)
        .filter(EntityIdentity.id == identity_id, EntityIdentity.user_id == user_id)
        .first()
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found.")
    _owned_source(identity.source_type, identity.source_id, user_id, db)  # type: ignore[arg-type]
    return identity


def _event_track_ids(event: Event | LiveEvent) -> list[int]:
    result: list[int] = []
    for value in event.involved_track_ids or []:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            result.append(int(value))
    return result


def _related_events(
    identity: EntityIdentity, track_ids: set[int], db: Session
) -> list[IdentityRelatedEventResponse]:
    if not track_ids:
        return []
    results: list[IdentityRelatedEventResponse] = []
    if identity.source_type == "analysis":
        rows = (
            db.query(Event)
            .filter(Event.analysis_id == identity.source_id)
            .order_by(Event.start_timestamp.asc())
            .all()
        )
        for event in rows:
            involved = _event_track_ids(event)
            if track_ids.intersection(involved):
                results.append(
                    IdentityRelatedEventResponse(
                        event_id=event.id,
                        id=event.id,
                        event_type=event.event_type,
                        category=event.category,
                        title=event.title,
                        timestamp_seconds=event.start_timestamp,
                        confidence=event.confidence,
                        severity=event.severity,
                        involved_track_ids=involved,
                        track_codes=[
                            f"T{value:03d}" for value in sorted(track_ids.intersection(involved))
                        ],
                    )
                )
    else:
        rows = (
            db.query(LiveEvent)
            .filter(LiveEvent.session_id == identity.source_id)
            .order_by(LiveEvent.timestamp_seconds.asc())
            .all()
        )
        for event in rows:
            involved = _event_track_ids(event)
            if track_ids.intersection(involved):
                results.append(
                    IdentityRelatedEventResponse(
                        event_id=event.id,
                        id=event.id,
                        event_type=event.event_type,
                        category=event.category,
                        title=event.title,
                        timestamp_seconds=event.timestamp_seconds,
                        confidence=event.confidence,
                        severity=event.severity,
                        involved_track_ids=involved,
                        track_codes=[
                            f"T{value:03d}" for value in sorted(track_ids.intersection(involved))
                        ],
                    )
                )
    return results


def _identity_response(
    identity: EntityIdentity, db: Session, include_details: bool = True
) -> EntityIdentityResponse:
    observations = (
        db.query(IdentityObservation)
        .filter(
            IdentityObservation.identity_id == identity.id,
            IdentityObservation.user_id == identity.user_id,
        )
        .order_by(IdentityObservation.first_seen_timestamp.asc())
        .all()
    )
    observation_responses = [
        IdentityObservationResponse(
            track_id=observation.track_id,
            track_code=f"T{observation.track_id:03d}",
            first_seen_timestamp=observation.first_seen_timestamp,
            last_seen_timestamp=observation.last_seen_timestamp,
            detection_count=observation.detection_count,
            match_confidence=observation.match_confidence,
            feature_quality=observation.feature_quality,
            matching_explanation=observation.matching_explanation,
            bbox=observation.bbox,
            evidence_url=(
                f"{get_settings().api_v1_prefix}/identities/{identity.id}/"
                f"observations/{observation.track_id}/evidence"
                if observation.evidence_path
                else None
            ),
        )
        for observation in observations
    ]
    legacy_observations = [
        IdentityTrackAppearanceCompatResponse(
            track_id=observation.track_id,
            track_code=f"T{observation.track_id:03d}",
            category=observation.class_name,
            first_seen_timestamp=observation.first_seen_timestamp,
            last_seen_timestamp=observation.last_seen_timestamp,
            detection_count=observation.detection_count,
            match_confidence=observation.match_confidence,
            match_status=identity.status,  # type: ignore[arg-type]
            matching_explanation=observation.matching_explanation,
            evidence_url=(
                f"{get_settings().api_v1_prefix}/identities/{identity.id}/"
                f"observations/{observation.track_id}/evidence"
                if observation.evidence_path
                else None
            ),
            manually_corrected="Manually reviewed" in observation.matching_explanation,
            correction_note=(
                observation.matching_explanation
                if "Manually reviewed" in observation.matching_explanation
                else None
            ),
        )
        for observation in observations
    ]
    track_ids = {observation.track_id for observation in observations}
    related_events = _related_events(identity, track_ids, db) if include_details else []
    merged_into_code = (
        db.query(EntityIdentity.identity_code)
        .filter(
            EntityIdentity.id == identity.merged_into_identity_id,
            EntityIdentity.user_id == identity.user_id,
        )
        .scalar()
        if identity.merged_into_identity_id
        else None
    )
    return EntityIdentityResponse(
        id=identity.id,
        source_type=identity.source_type,  # type: ignore[arg-type]
        source_id=identity.source_id,
        identity_code=identity.identity_code,
        entity_type=identity.entity_type,  # type: ignore[arg-type]
        class_name=identity.class_name,
        category=identity.class_name,
        status=identity.status,  # type: ignore[arg-type]
        first_seen_timestamp=identity.first_seen_timestamp,
        last_seen_timestamp=identity.last_seen_timestamp,
        appearance_count=len(observations),
        associated_track_ids=sorted(track_ids),
        associated_track_codes=[f"T{track_id:03d}" for track_id in sorted(track_ids)],
        matching_confidence=identity.matching_confidence,
        matching_explanation=identity.matching_explanation,
        feature_reference=identity.feature_reference,
        evidence_refs=[
            item.evidence_url for item in observation_responses if item.evidence_url
        ],
        evidence_urls=[
            item.evidence_url for item in observation_responses if item.evidence_url
        ],
        related_event_count=len(related_events),
        merged_into_code=merged_into_code,
        observations=observation_responses if include_details else [],
        track_appearances=legacy_observations if include_details else [],
        related_events=related_events,
    )


@router.get(
    "",
    response_model=IdentitySearchResponse,
    summary="Search source-scoped anonymous people and object identities",
)
def search_identities(
    source_type: IdentitySourceType,
    source_id: str,
    entity_type: IdentityEntityType | None = None,
    identity_code: str | None = None,
    status_filter: IdentityStatus | None = Query(default=None, alias="status"),
    min_appearances: int = Query(default=1, ge=0),
    first_seen_after: float | None = Query(default=None, ge=0),
    last_seen_before: float | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentitySearchResponse:
    """Return unique identities only within one owned recording or live session."""
    _owned_source(source_type, source_id, current_user.id, db)
    base = db.query(EntityIdentity).filter(
        EntityIdentity.user_id == current_user.id,
        EntityIdentity.source_type == source_type,
        EntityIdentity.source_id == source_id,
        EntityIdentity.appearance_count > 0,
    )
    total_people = base.filter(EntityIdentity.entity_type == "person").count()
    total_objects = base.filter(EntityIdentity.entity_type == "object").count()

    query = base.filter(EntityIdentity.appearance_count >= min_appearances)
    if entity_type:
        query = query.filter(EntityIdentity.entity_type == entity_type)
    if status_filter:
        query = query.filter(EntityIdentity.status == status_filter)
    if identity_code:
        query = query.filter(EntityIdentity.identity_code == identity_code.strip().upper())
    if first_seen_after is not None:
        query = query.filter(EntityIdentity.first_seen_timestamp >= first_seen_after)
    if last_seen_before is not None:
        query = query.filter(EntityIdentity.last_seen_timestamp <= last_seen_before)
    total = query.count()
    rows = (
        query.order_by(EntityIdentity.first_seen_timestamp.asc(), EntityIdentity.identity_code.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return IdentitySearchResponse(
        source_type=source_type,
        source_id=source_id,
        total_unique_people=total_people,
        total_unique_objects=total_objects,
        total=total,
        limit=limit,
        offset=offset,
        items=[_identity_response(row, db, include_details=False) for row in rows],
    )


@router.get(
    "/counts",
    response_model=IdentityCountsResponse,
    summary="Get source-scoped unique identity counts",
)
def get_identity_counts(
    source_type: IdentitySourceType,
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityCountsResponse:
    _owned_source(source_type, source_id, current_user.id, db)
    identities = (
        db.query(EntityIdentity)
        .filter(
            EntityIdentity.user_id == current_user.id,
            EntityIdentity.source_type == source_type,
            EntityIdentity.source_id == source_id,
            EntityIdentity.appearance_count > 0,
        )
        .all()
    )
    return IdentityCountsResponse(
        unique_people=sum(row.entity_type == "person" for row in identities),
        unique_objects=sum(row.entity_type == "object" for row in identities),
        confirmed=sum(row.status == "confirmed" for row in identities),
        probable=sum(row.status == "probable" for row in identities),
        unknown=sum(row.status == "unknown" for row in identities),
    )


@router.get(
    "/{identity_id}",
    response_model=EntityIdentityResponse,
    summary="Get identity appearances, associated events, and evidence",
)
def get_identity(
    identity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityIdentityResponse:
    identity = _identity_by_id(identity_id, current_user.id, db)
    return _identity_response(identity, db)


def _refresh_identity_summary(identity: EntityIdentity, db: Session) -> None:
    observations = (
        db.query(IdentityObservation)
        .filter(IdentityObservation.identity_id == identity.id)
        .all()
    )
    identity.associated_track_ids = sorted({row.track_id for row in observations})
    identity.appearance_count = len(observations)
    if not observations:
        identity.status = "unknown"
        identity.matching_confidence = 0.0
        identity.matching_explanation = "No track appearances remain assigned to this identity."
        identity.descriptor_sample_count = 0
        identity.appearance_descriptor = None
        identity.appearance_signature = None
        identity.evidence_refs = []
        return
    identity.first_seen_timestamp = min(row.first_seen_timestamp for row in observations)
    identity.last_seen_timestamp = max(row.last_seen_timestamp for row in observations)
    identity.appearance_signature = aggregate_signatures(
        [row.appearance_signature for row in observations if row.appearance_signature]
    )
    identity.appearance_descriptor = identity.appearance_signature
    identity.descriptor_sample_count = sum(
        row.appearance_signature is not None for row in observations
    )
    identity.category = observations[0].class_name
    identity.class_name = observations[0].class_name
    identity.evidence_refs = [
        f"{get_settings().api_v1_prefix}/identities/{identity.id}/"
        f"observations/{row.track_id}/evidence"
        for row in observations
        if row.evidence_path
    ]


def _update_analysis_track_labels(
    analysis_id: str, track_id: int, target: EntityIdentity
) -> None:
    analysis_dir = get_settings().resolved_processed_dir / analysis_id
    for filename, collection_key, id_key in (
        ("detections.json", "frames", "track_id"),
        ("tracks.json", "tracks", "track_id"),
    ):
        path = analysis_dir / filename
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if filename == "detections.json":
            records = [
                detection
                for frame in payload.get(collection_key, [])
                for detection in frame.get("detections", [])
            ]
        else:
            records = payload.get(collection_key, [])
        for record in records:
            if record.get(id_key) is not None and int(record[id_key]) == track_id:
                record.update(
                    {
                        "identity_id": target.id,
                        "identity_code": target.identity_code,
                        "identity_status": "confirmed",
                        "identity_confidence": 1.0,
                    }
                )
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, path)


@router.patch(
    "/{identity_id}/observations/{track_id}",
    response_model=IdentityCorrectionResponse,
    summary="Manually confirm or reassign a source-local track identity",
)
def correct_identity_assignment(
    identity_id: str,
    track_id: int,
    payload: IdentityCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityCorrectionResponse:
    current = _identity_by_id(identity_id, current_user.id, db)
    observation = (
        db.query(IdentityObservation)
        .filter(
            IdentityObservation.identity_id == current.id,
            IdentityObservation.track_id == track_id,
            IdentityObservation.user_id == current_user.id,
        )
        .first()
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="Track appearance not found for this identity.")
    target = _identity_by_id(payload.target_identity_id, current_user.id, db)
    if (
        target.source_type != current.source_type
        or target.source_id != current.source_id
        or target.entity_type != current.entity_type
    ):
        raise HTTPException(
            status_code=400,
            detail="Manual corrections must remain within the same source and entity type.",
        )

    return _apply_identity_correction(
        current=current,
        target=target,
        observation=observation,
        current_user=current_user,
        db=db,
    )


def _apply_identity_correction(
    *,
    current: EntityIdentity,
    target: EntityIdentity,
    observation: IdentityObservation,
    current_user: User,
    db: Session,
    correction_note: str | None = None,
) -> IdentityCorrectionResponse:
    previous_code = current.identity_code
    observation.identity_id = target.id
    observation.match_confidence = 1.0
    explanation = correction_note or "Manually reviewed and assigned by the authenticated owner."
    observation.matching_explanation = explanation
    current.status = "confirmed"
    target.status = "confirmed"
    target.matching_confidence = 1.0
    target.matching_explanation = (
        f"{explanation} Associated ByteTrack IDs remain recorded."
    )
    db.flush()
    _refresh_identity_summary(current, db)
    _refresh_identity_summary(target, db)
    if current.source_type == "analysis":
        _update_analysis_track_labels(current.source_id, observation.track_id, target)
    db.commit()
    db.refresh(target)
    if current.source_type == "live_session":
        refresh_live_identity_matcher(
            session_id=current.source_id,
            user_id=current_user.id,
            db=db,
        )
    return IdentityCorrectionResponse(
        identity=_identity_response(target, db),
        corrected_track_id=observation.track_id,
        previous_identity_code=previous_code,
        correction=(
            f"Track T{observation.track_id:03d} was manually assigned to {target.identity_code}. "
            "The original tracking ID is unchanged."
        ),
    )


@router.patch(
    "/{identity_id}/tracks/{track_id}",
    response_model=IdentityCorrectionResponse,
    summary="Correct an identity using the legacy track route",
)
def correct_identity_track_legacy(
    identity_id: str,
    track_id: int,
    payload: IdentityLegacyCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityCorrectionResponse:
    current = _identity_by_id(identity_id, current_user.id, db)
    observation = (
        db.query(IdentityObservation)
        .filter(
            IdentityObservation.identity_id == current.id,
            IdentityObservation.track_id == track_id,
            IdentityObservation.user_id == current_user.id,
        )
        .first()
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="Track appearance not found for this identity.")
    if payload.create_new_identity == bool(payload.target_identity_id):
        raise HTTPException(
            status_code=400,
            detail="Choose either an existing target identity or create a new identity.",
        )

    if payload.create_new_identity:
        prefix = "P" if current.entity_type == "person" else "O"
        codes = (
            db.query(EntityIdentity.identity_code)
            .filter(
                EntityIdentity.user_id == current_user.id,
                EntityIdentity.source_type == current.source_type,
                EntityIdentity.source_id == current.source_id,
                EntityIdentity.identity_code.like(f"{prefix}%"),
            )
            .all()
        )
        next_number = max(
            (
                int(code[0][1:])
                for code in codes
                if code[0][1:].isdigit()
            ),
            default=0,
        ) + 1
        target = EntityIdentity(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            source_type=current.source_type,
            source_id=current.source_id,
            analysis_id=current.source_id if current.source_type == "analysis" else None,
            live_session_id=current.source_id if current.source_type == "live_session" else None,
            identity_code=f"{prefix}{next_number:03d}",
            entity_type=current.entity_type,
            category=observation.class_name,
            class_name=observation.class_name,
            status="confirmed",
            first_seen_timestamp=observation.first_seen_timestamp,
            last_seen_timestamp=observation.last_seen_timestamp,
            appearance_count=1,
            descriptor_sample_count=1 if observation.appearance_signature else 0,
            associated_track_ids=[observation.track_id],
            appearance_descriptor=observation.appearance_signature,
            appearance_signature=observation.appearance_signature,
            last_position=observation.last_position,
            feature_reference=current.feature_reference,
            matching_confidence=1.0,
            matching_explanation=payload.correction_note
            or "Created as a separate identity by authenticated owner review.",
            evidence_refs=[],
        )
        db.add(target)
        db.flush()
    else:
        if payload.target_identity_id is None:
            raise HTTPException(
                status_code=400,
                detail="A target identity is required unless creating a new identity.",
            )
        target = _identity_by_id(payload.target_identity_id, current_user.id, db)
        if (
            target.source_type != current.source_type
            or target.source_id != current.source_id
            or target.entity_type != current.entity_type
        ):
            raise HTTPException(
                status_code=400,
                detail="Manual corrections must remain within the same source and entity type.",
            )
        if payload.correction_note:
            target.matching_explanation = payload.correction_note

    result = _apply_identity_correction(
        current=current,
        target=target,
        observation=observation,
        current_user=current_user,
        db=db,
        correction_note=payload.correction_note,
    )
    if payload.create_new_identity:
        result.correction = (
            f"Track T{observation.track_id:03d} was separated into new identity "
            f"{target.identity_code}; the original tracking ID is unchanged."
        )
    return result


@router.get(
    "/{identity_id}/observations/{track_id}/evidence",
    # Keep the original URL available to existing clients.
)
@router.get(
    "/{identity_id}/tracks/{track_id}/evidence",
    summary="Fetch privacy-preserving appearance evidence for an owned identity track",
)
def get_identity_observation_evidence(
    identity_id: str,
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    identity = _identity_by_id(identity_id, current_user.id, db)
    observation = (
        db.query(IdentityObservation)
        .filter(
            IdentityObservation.identity_id == identity.id,
            IdentityObservation.track_id == track_id,
            IdentityObservation.user_id == current_user.id,
        )
        .first()
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="Identity evidence not found.")
    try:
        path = get_identity_evidence_path(observation=observation, identity=identity)
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/jpeg", filename=f"{identity.identity_code}-T{track_id:03d}.jpg")