from dataclasses import dataclass
import logging
import math
from pathlib import Path
import threading
from typing import Any, Literal
import uuid

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.identity import EntityIdentity, IdentityTrackAssociation

logger = logging.getLogger(__name__)
SourceType = Literal["analysis", "live_session"]
PERSON_MATCH_THRESHOLD = 0.87
OBJECT_MATCH_THRESHOLD = 0.92
PERSON_UNCERTAIN_THRESHOLD = 0.68
OBJECT_UNCERTAIN_THRESHOLD = 0.76
PERSON_AMBIGUITY_MARGIN = 0.05
OBJECT_AMBIGUITY_MARGIN = 0.08
_identity_lock = threading.RLock()


@dataclass(frozen=True)
class TrackAppearanceProfile:
    track_id: int
    category: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    detection_count: int
    descriptor: dict[str, Any] | None
    descriptor_sample_count: int
    evidence_filename: str | None

    @property
    def entity_type(self) -> Literal["person", "object"]:
        return "person" if self.category.casefold() == "person" else "object"


def _entity_crop(
    frame: np.ndarray,
    bbox: tuple[float, float, float, float],
    entity_type: str,
) -> tuple[np.ndarray, float] | None:
    if frame.ndim != 3 or frame.shape[2] != 3:
        return None
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    left = max(0, min(width, int(math.floor(x1))))
    right = max(0, min(width, int(math.ceil(x2))))
    top = max(0, min(height, int(math.floor(y1))))
    bottom = max(0, min(height, int(math.ceil(y2))))
    box_width = right - left
    box_height = bottom - top
    if box_width < 16 or box_height < 20:
        return None

    crop_top = top + int(box_height * 0.18) if entity_type == "person" else top
    crop = frame[crop_top:bottom, left:right]
    if crop.size == 0:
        return None
    quality = min(1.0, math.sqrt((box_width * box_height) / 4096.0))
    return crop, quality


def extract_appearance_descriptor(
    frame: np.ndarray,
    bbox: tuple[float, float, float, float],
    category: str,
    confidence: float = 1.0,
) -> dict[str, Any] | None:
    """Create a small CPU-only color/texture/shape signature; no facial features are used."""
    entity_type = "person" if category.casefold() == "person" else "object"
    crop_info = _entity_crop(frame, bbox, entity_type)
    if crop_info is None:
        return None
    crop, size_quality = crop_info
    crop_height, crop_width = crop.shape[:2]
    if crop_width < 12 or crop_height < 12:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv_hist = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).reshape(-1)
    value_hist = cv2.calcHist([hsv], [2], None, [8], [0, 256]).reshape(-1)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(grad_x, grad_y, angleInDegrees=True)
    edge_hist, _ = np.histogram(
        angle,
        bins=8,
        range=(0.0, 360.0),
        weights=magnitude,
    )

    def normalized(values: np.ndarray) -> list[float]:
        total = float(values.sum())
        if total <= 0:
            return [0.0] * len(values)
        return [round(float(value) / total, 6) for value in values]

    def normalized_entropy(values: list[float]) -> float:
        probabilities = np.asarray(values, dtype=np.float64)
        probabilities = probabilities[probabilities > 0]
        if probabilities.size < 2:
            return 0.0
        entropy = -float(np.sum(probabilities * np.log(probabilities)))
        return min(1.0, entropy / math.log(len(values)))

    color_hist = normalized(hsv_hist)
    normalized_value_hist = normalized(value_hist)
    normalized_edge_hist = normalized(edge_hist.astype(np.float32))
    distinctiveness = max(
        normalized_entropy(color_hist),
        normalized_entropy(normalized_value_hist),
        normalized_entropy(normalized_edge_hist),
    )

    top_hist: list[float] = []
    bottom_hist: list[float] = []
    if entity_type == "person":
        split = max(1, crop_height // 2)
        top_hsv = cv2.cvtColor(crop[:split], cv2.COLOR_BGR2HSV)
        bottom_hsv = cv2.cvtColor(crop[split:], cv2.COLOR_BGR2HSV)
        top_hist = normalized(
            cv2.calcHist([top_hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).reshape(-1)
        )
        bottom_hist = normalized(
            cv2.calcHist([bottom_hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).reshape(-1)
        )

    box_height = max(1.0, bbox[3] - bbox[1])
    box_width = max(1.0, bbox[2] - bbox[0])
    return {
        "version": 1,
        "hsv_hist": color_hist,
        "value_hist": normalized_value_hist,
        "edge_hist": normalized_edge_hist,
        "top_hist": top_hist,
        "bottom_hist": bottom_hist,
        "aspect_ratio": round(box_width / box_height, 5),
        "quality": round(size_quality * min(1.0, max(0.0, confidence)), 4),
        "distinctiveness": round(distinctiveness, 4),
    }


def average_appearance_descriptors(
    descriptors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    valid = [item for item in descriptors if item and item.get("version") == 1]
    if not valid:
        return None
    result: dict[str, Any] = {"version": 1}
    for key in ("hsv_hist", "value_hist", "edge_hist", "top_hist", "bottom_hist"):
        vectors = [np.asarray(item[key], dtype=np.float64) for item in valid if item.get(key)]
        if not vectors:
            result[key] = []
            continue
        mean = np.mean(vectors, axis=0)
        total = float(mean.sum())
        result[key] = [round(float(value) / total, 6) for value in mean] if total > 0 else []
    result["aspect_ratio"] = round(
        sum(float(item["aspect_ratio"]) for item in valid) / len(valid),
        5,
    )
    result["quality"] = round(
        sum(float(item.get("quality", 0.0)) for item in valid) / len(valid),
        4,
    )
    result["distinctiveness"] = round(
        sum(float(item.get("distinctiveness", 0.0)) for item in valid) / len(valid),
        4,
    )
    return result


def _histogram_intersection(left: Any, right: Any) -> float:
    try:
        left_values = np.asarray(left, dtype=np.float64)
        right_values = np.asarray(right, dtype=np.float64)
        if left_values.shape != right_values.shape or left_values.size == 0:
            return 0.0
        return float(np.minimum(left_values, right_values).sum())
    except (TypeError, ValueError):
        return 0.0


def appearance_similarity(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    entity_type: str,
) -> float:
    """Return a documented heuristic similarity (not a probability or identity proof)."""
    if not left or not right or left.get("version") != 1 or right.get("version") != 1:
        return 0.0
    color = _histogram_intersection(left.get("hsv_hist"), right.get("hsv_hist"))
    value = _histogram_intersection(left.get("value_hist"), right.get("value_hist"))
    texture = _histogram_intersection(left.get("edge_hist"), right.get("edge_hist"))
    try:
        left_aspect = max(0.01, float(left["aspect_ratio"]))
        right_aspect = max(0.01, float(right["aspect_ratio"]))
        shape = math.exp(-abs(math.log(left_aspect / right_aspect)))
    except (KeyError, TypeError, ValueError):
        shape = 0.0

    if entity_type == "person":
        top = _histogram_intersection(left.get("top_hist"), right.get("top_hist"))
        bottom = _histogram_intersection(left.get("bottom_hist"), right.get("bottom_hist"))
        appearance = 0.45 * color + 0.25 * top + 0.20 * bottom + 0.05 * value + 0.05 * texture
        score = 0.92 * appearance + 0.08 * shape
    else:
        appearance = 0.65 * color + 0.20 * value + 0.15 * texture
        score = 0.80 * appearance + 0.20 * shape
    quality = min(float(left.get("quality", 0.0)), float(right.get("quality", 0.0)))
    return round(max(0.0, min(1.0, score * math.sqrt(max(0.0, quality)))), 4)


def _thresholds(entity_type: str) -> tuple[float, float, float]:
    if entity_type == "person":
        return (
            PERSON_MATCH_THRESHOLD,
            PERSON_UNCERTAIN_THRESHOLD,
            PERSON_AMBIGUITY_MARGIN,
        )
    return (
        OBJECT_MATCH_THRESHOLD,
        OBJECT_UNCERTAIN_THRESHOLD,
        OBJECT_AMBIGUITY_MARGIN,
    )


def _next_identity_code(
    db: Session,
    source_type: SourceType,
    source_id: str,
    entity_type: str,
) -> str:
    prefix = "P" if entity_type == "person" else "O"
    codes = (
        db.query(EntityIdentity.identity_code)
        .filter(
            EntityIdentity.source_type == source_type,
            EntityIdentity.source_id == source_id,
            EntityIdentity.identity_code.like(f"{prefix}%"),
        )
        .all()
    )
    highest = 0
    for (code,) in codes:
        try:
            highest = max(highest, int(str(code)[1:]))
        except ValueError:
            logger.warning("Ignoring malformed identity code %s in source %s", code, source_id)
    return f"{prefix}{highest + 1:03d}"


def _candidate_matches(
    db: Session,
    source_type: SourceType,
    source_id: str,
    entity_type: str,
    category: str,
    descriptor: dict[str, Any] | None,
    first_seen_timestamp: float,
    exclude_identity_id: str | None = None,
) -> list[tuple[float, EntityIdentity]]:
    if descriptor is None or float(descriptor.get("quality", 0.0)) < 0.18:
        return []
    query = db.query(EntityIdentity).filter(
        EntityIdentity.source_type == source_type,
        EntityIdentity.source_id == source_id,
        EntityIdentity.entity_type == entity_type,
        EntityIdentity.appearance_count > 0,
        EntityIdentity.merged_into_identity_id.is_(None),
    )
    if entity_type == "object":
        query = query.filter(EntityIdentity.category == category)
    identities = query.order_by(EntityIdentity.first_seen_timestamp.asc()).all()
    matches: list[tuple[float, EntityIdentity]] = []
    for identity in identities:
        if identity.id == exclude_identity_id:
            continue
        if entity_type == "object" and (
            float(descriptor.get("distinctiveness", 0.0)) < 0.12
            or float((identity.appearance_descriptor or {}).get("distinctiveness", 0.0)) < 0.12
        ):
            continue
        if identity.last_seen_timestamp >= first_seen_timestamp - 0.25:
            continue
        score = appearance_similarity(descriptor, identity.appearance_descriptor, entity_type)
        matches.append((score, identity))
    return sorted(matches, key=lambda match: match[0], reverse=True)


def _make_identity(
    *,
    user_id: int,
    source_type: SourceType,
    source_id: str,
    analysis_id: str | None,
    live_session_id: str | None,
    identity_code: str,
    entity_type: str,
    category: str,
    first_seen_timestamp: float,
    last_seen_timestamp: float,
    descriptor: dict[str, Any] | None,
    descriptor_sample_count: int,
    matching_confidence: float | None,
    candidate_code: str | None,
    matching_explanation: str,
) -> EntityIdentity:
    return EntityIdentity(
        id=str(uuid.uuid4()),
        user_id=user_id,
        source_type=source_type,
        source_id=source_id,
        analysis_id=analysis_id,
        live_session_id=live_session_id,
        identity_code=identity_code,
        entity_type=entity_type,
        category=category,
        first_seen_timestamp=first_seen_timestamp,
        last_seen_timestamp=last_seen_timestamp,
        appearance_count=1,
        descriptor_sample_count=descriptor_sample_count,
        matching_confidence=matching_confidence,
        status="unknown",
        appearance_descriptor=descriptor,
        evidence_refs=[],
        matching_explanation=matching_explanation,
        unresolved_candidate_code=candidate_code,
    )


def _blend_descriptor(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    existing_count: int,
    incoming_count: int,
) -> dict[str, Any] | None:
    if incoming is None:
        return existing
    if existing is None or existing_count <= 0:
        return incoming
    weights = (max(0, existing_count), max(1, incoming_count))
    result: dict[str, Any] = {"version": 1}
    for key in ("hsv_hist", "value_hist", "edge_hist", "top_hist", "bottom_hist"):
        previous = existing.get(key) or []
        current = incoming.get(key) or []
        if not previous or not current or len(previous) != len(current):
            result[key] = current or previous
            continue
        merged = (
            np.asarray(previous, dtype=np.float64) * weights[0]
            + np.asarray(current, dtype=np.float64) * weights[1]
        ) / max(1, sum(weights))
        total = float(merged.sum())
        result[key] = [round(float(value) / total, 6) for value in merged] if total else []
    total_samples = max(1, sum(weights))
    result["aspect_ratio"] = round(
        (
            float(existing.get("aspect_ratio", 1.0)) * weights[0]
            + float(incoming.get("aspect_ratio", 1.0)) * weights[1]
        )
        / total_samples,
        5,
    )
    result["quality"] = round(
        (
            float(existing.get("quality", 0.0)) * weights[0]
            + float(incoming.get("quality", 0.0)) * weights[1]
        )
        / total_samples,
        4,
    )
    result["distinctiveness"] = round(
        (
            float(existing.get("distinctiveness", 0.0)) * weights[0]
            + float(incoming.get("distinctiveness", 0.0)) * weights[1]
        )
        / total_samples,
        4,
    )
    return result


def _save_live_identity_evidence(
    *,
    source_id: str,
    track_id: int,
    frame_index: int,
    frame: np.ndarray,
    bbox: tuple[float, float, float, float],
    entity_type: str,
) -> str | None:
    crop_info = _entity_crop(frame, bbox, entity_type)
    if crop_info is None:
        return None
    crop, _quality = crop_info
    max_width = 320
    if crop.shape[1] > max_width:
        crop = cv2.resize(
            crop,
            (max_width, max(1, round(crop.shape[0] * max_width / crop.shape[1]))),
            interpolation=cv2.INTER_AREA,
        )
    settings = get_settings()
    live_root = settings.resolved_live_dir.resolve()
    session_dir = (live_root / source_id).resolve()
    evidence_dir = (session_dir / "identity-evidence").resolve()
    if session_dir.parent != live_root or evidence_dir.parent != session_dir:
        raise ValueError("Invalid live identity evidence storage path.")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    filename = f"identity_t{track_id}_f{frame_index}.jpg"
    target_path = (evidence_dir / filename).resolve()
    if target_path.parent != evidence_dir:
        raise ValueError("Invalid live identity evidence filename.")
    if target_path.exists():
        return filename
    ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return None
    target_path.write_bytes(encoded.tobytes())
    return filename


def _make_track_association(
    *,
    identity: EntityIdentity,
    source_type: SourceType,
    source_id: str,
    track_id: int,
    category: str,
    first_seen_timestamp: float,
    last_seen_timestamp: float,
    detection_count: int,
    descriptor: dict[str, Any] | None,
    descriptor_sample_count: int,
    match_confidence: float | None,
    status: str,
    explanation: str,
    candidate_code: str | None,
    evidence_reference: str | None,
) -> IdentityTrackAssociation:
    if evidence_reference:
        identity.evidence_refs = list(
            dict.fromkeys([*identity.evidence_refs, evidence_reference])
        )
    return IdentityTrackAssociation(
        id=str(uuid.uuid4()),
        identity=identity,
        source_type=source_type,
        source_id=source_id,
        track_id=track_id,
        category=category,
        first_seen_timestamp=first_seen_timestamp,
        last_seen_timestamp=last_seen_timestamp,
        detection_count=detection_count,
        descriptor_sample_count=descriptor_sample_count,
        appearance_descriptor=descriptor,
        match_confidence=match_confidence,
        match_status=status,
        matching_explanation=explanation,
        unresolved_candidate_code=candidate_code,
        evidence_reference=evidence_reference,
    )


def _assign_recorded_profile(
    db: Session,
    *,
    user_id: int,
    analysis_id: str,
    profile: TrackAppearanceProfile,
) -> tuple[EntityIdentity, IdentityTrackAssociation]:
    entity_type = profile.entity_type
    matches = _candidate_matches(
        db,
        "analysis",
        analysis_id,
        entity_type,
        profile.category,
        profile.descriptor,
        profile.first_seen_timestamp,
    )
    accepted_threshold, uncertain_threshold, margin_threshold = _thresholds(entity_type)
    best_score, best_identity = matches[0] if matches else (0.0, None)
    margin = best_score - (matches[1][0] if len(matches) > 1 else 0.0)
    can_match = (
        best_identity is not None
        and best_score >= accepted_threshold
        and margin >= margin_threshold
    )
    if can_match and best_identity is not None:
        identity = best_identity
        old_count = identity.descriptor_sample_count
        identity.appearance_descriptor = _blend_descriptor(
            identity.appearance_descriptor,
            profile.descriptor,
            old_count,
            profile.descriptor_sample_count,
        )
        identity.descriptor_sample_count += profile.descriptor_sample_count
        identity.first_seen_timestamp = min(
            identity.first_seen_timestamp,
            profile.first_seen_timestamp,
        )
        identity.last_seen_timestamp = max(
            identity.last_seen_timestamp,
            profile.last_seen_timestamp,
        )
        identity.appearance_count += 1
        identity.matching_confidence = best_score
        if identity.status != "confirmed":
            identity.status = "probable"
        identity.matching_explanation = (
            f"Track T{profile.track_id:03d} was associated by appearance similarity "
            f"{best_score:.2f}; this is a probable visual match, not proof of identity."
        )
        if profile.evidence_filename:
            identity.evidence_refs = list(dict.fromkeys(
                [*identity.evidence_refs, profile.evidence_filename]
            ))
        explanation = identity.matching_explanation
        association_status = "probable"
        candidate_code = None
        match_confidence: float | None = best_score
    else:
        candidate_code = (
            best_identity.identity_code
            if best_identity is not None and best_score >= uncertain_threshold
            else None
        )
        if profile.descriptor is None:
            explanation = (
                "Appearance evidence was too small or unavailable; this track remains an "
                "unresolved source-local identity."
            )
        elif candidate_code:
            explanation = (
                f"Best prior appearance similarity was {best_score:.2f}, below the "
                "automatic-match confidence/margin requirements; no identity was merged."
            )
        elif best_identity is None:
            explanation = (
                "No earlier non-overlapping identity in this video was available for comparison."
            )
        else:
            explanation = (
                f"No prior identity met the configured appearance threshold "
                f"(best similarity {best_score:.2f}); a separate ID was retained."
            )
        identity = _make_identity(
            user_id=user_id,
            source_type="analysis",
            source_id=analysis_id,
            analysis_id=analysis_id,
            live_session_id=None,
            identity_code=_next_identity_code(db, "analysis", analysis_id, entity_type),
            entity_type=entity_type,
            category=profile.category,
            first_seen_timestamp=profile.first_seen_timestamp,
            last_seen_timestamp=profile.last_seen_timestamp,
            descriptor=profile.descriptor,
            descriptor_sample_count=profile.descriptor_sample_count,
            matching_confidence=best_score if best_identity is not None else None,
            candidate_code=candidate_code,
            matching_explanation=explanation,
        )
        db.add(identity)
        association_status = "unknown"
        match_confidence = best_score if best_identity is not None else None

    association = _make_track_association(
        identity=identity,
        source_type="analysis",
        source_id=analysis_id,
        track_id=profile.track_id,
        category=profile.category,
        first_seen_timestamp=profile.first_seen_timestamp,
        last_seen_timestamp=profile.last_seen_timestamp,
        detection_count=profile.detection_count,
        descriptor=profile.descriptor,
        descriptor_sample_count=profile.descriptor_sample_count,
        match_confidence=match_confidence,
        status=association_status,
        explanation=explanation if not can_match else identity.matching_explanation,
        candidate_code=candidate_code,
        evidence_reference=profile.evidence_filename,
    )
    db.add(association)
    return identity, association


def associate_recorded_track_appearances(
    db: Session,
    *,
    user_id: int,
    analysis_id: str,
    profiles: list[TrackAppearanceProfile],
) -> dict[int, str]:
    """Build a chronological source-local identity registry for a completed analysis."""
    with _identity_lock:
        db.query(IdentityTrackAssociation).filter(
            IdentityTrackAssociation.source_type == "analysis",
            IdentityTrackAssociation.source_id == analysis_id,
        ).delete(synchronize_session=False)
        db.query(EntityIdentity).filter(
            EntityIdentity.source_type == "analysis",
            EntityIdentity.source_id == analysis_id,
        ).delete(synchronize_session=False)
        identity_codes: dict[int, str] = {}
        for profile in sorted(
            profiles,
            key=lambda item: (item.first_seen_timestamp, item.track_id),
        ):
            identity, _association = _assign_recorded_profile(
                db,
                user_id=user_id,
                analysis_id=analysis_id,
                profile=profile,
            )
            db.flush()
            identity_codes[profile.track_id] = identity.identity_code
        return identity_codes


def get_track_identity_codes(
    db: Session,
    *,
    source_type: SourceType,
    source_id: str,
) -> dict[int, str]:
    rows = (
        db.query(IdentityTrackAssociation.track_id, EntityIdentity.identity_code)
        .join(EntityIdentity, IdentityTrackAssociation.identity_id == EntityIdentity.id)
        .filter(
            IdentityTrackAssociation.source_type == source_type,
            IdentityTrackAssociation.source_id == source_id,
            EntityIdentity.appearance_count > 0,
            EntityIdentity.merged_into_identity_id.is_(None),
        )
        .all()
    )
    return {int(track_id): str(identity_code) for track_id, identity_code in rows}


def _rebuild_identity_aggregate(db: Session, identity: EntityIdentity) -> None:
    associations = (
        db.query(IdentityTrackAssociation)
        .filter(IdentityTrackAssociation.identity_id == identity.id)
        .order_by(IdentityTrackAssociation.first_seen_timestamp.asc())
        .all()
    )
    if not associations:
        identity.appearance_count = 0
        identity.descriptor_sample_count = 0
        identity.appearance_descriptor = None
        identity.evidence_refs = []
        return
    identity.appearance_count = len(associations)
    identity.first_seen_timestamp = min(item.first_seen_timestamp for item in associations)
    identity.last_seen_timestamp = max(item.last_seen_timestamp for item in associations)
    descriptors = [
        (item.appearance_descriptor, item.descriptor_sample_count)
        for item in associations
        if item.appearance_descriptor
    ]
    aggregate: dict[str, Any] | None = None
    count = 0
    for descriptor, weight in descriptors:
        aggregate = _blend_descriptor(aggregate, descriptor, count, weight)
        count += max(1, weight)
    identity.appearance_descriptor = aggregate
    identity.descriptor_sample_count = count
    identity.evidence_refs = list(
        dict.fromkeys(item.evidence_reference for item in associations if item.evidence_reference)
    )


def _try_upgrade_live_association(
    db: Session,
    association: IdentityTrackAssociation,
) -> None:
    if (
        association.manually_corrected
        or association.match_status != "unknown"
        or association.descriptor_sample_count < 2
        or association.appearance_descriptor is None
    ):
        return
    identity = association.identity
    entity_type = identity.entity_type
    matches = _candidate_matches(
        db,
        "live_session",
        association.source_id,
        entity_type,
        association.category,
        association.appearance_descriptor,
        association.first_seen_timestamp,
        exclude_identity_id=identity.id,
    )
    accepted_threshold, _uncertain_threshold, margin_threshold = _thresholds(entity_type)
    if not matches:
        return
    best_score, target = matches[0]
    margin = best_score - (matches[1][0] if len(matches) > 1 else 0.0)
    if best_score < accepted_threshold or margin < margin_threshold:
        return

    identity_id = identity.id
    association.identity = target
    association.match_status = "probable"
    association.match_confidence = best_score
    association.unresolved_candidate_code = None
    association.matching_explanation = (
        f"Track T{association.track_id:03d} was associated by appearance similarity "
        f"{best_score:.2f} after additional observations; this remains a probable visual match."
    )
    target.matching_confidence = best_score
    if target.status != "confirmed":
        target.status = "probable"
    target.matching_explanation = association.matching_explanation
    _rebuild_identity_aggregate(db, target)
    _rebuild_identity_aggregate(db, identity)
    if identity.appearance_count == 0:
        identity.merged_into_identity_id = target.id
        identity.matching_explanation = (
            f"This provisional identity was later associated with {target.identity_code} "
            "after additional appearance observations."
        )


def update_live_track_appearances(
    db: Session,
    *,
    user_id: int,
    session_id: str,
    frame_index: int,
    timestamp_seconds: float,
    frame: np.ndarray,
    detections: list[Any],
) -> dict[int, str]:
    """Persist per-session tracked appearances and return labels for this captured frame."""
    with _identity_lock:
        identity_codes: dict[int, str] = {}
        next_identity_numbers: dict[str, int] = {}
        for detection in detections:
            track_id = detection.track_id
            if track_id is None:
                continue
            category = str(detection.class_name)
            entity_type = "person" if category.casefold() == "person" else "object"
            bbox = (
                detection.bbox.x1,
                detection.bbox.y1,
                detection.bbox.x2,
                detection.bbox.y2,
            )
            association = (
                db.query(IdentityTrackAssociation)
                .filter(
                    IdentityTrackAssociation.source_type == "live_session",
                    IdentityTrackAssociation.source_id == session_id,
                    IdentityTrackAssociation.track_id == int(track_id),
                )
                .first()
            )
            should_sample = association is None or association.detection_count % 3 == 0
            descriptor = (
                extract_appearance_descriptor(frame, bbox, category, detection.confidence)
                if should_sample
                else None
            )
            evidence_reference = None
            if association is None or not association.evidence_reference:
                evidence_reference = _save_live_identity_evidence(
                    source_id=session_id,
                    track_id=int(track_id),
                    frame_index=frame_index,
                    frame=frame,
                    bbox=bbox,
                    entity_type=entity_type,
                )

            if association is None:
                profile = TrackAppearanceProfile(
                    track_id=int(track_id),
                    category=category,
                    first_seen_timestamp=timestamp_seconds,
                    last_seen_timestamp=timestamp_seconds,
                    detection_count=1,
                    descriptor=descriptor,
                    descriptor_sample_count=1 if descriptor else 0,
                    evidence_filename=evidence_reference,
                )
                matches = _candidate_matches(
                    db,
                    "live_session",
                    session_id,
                    entity_type,
                    category,
                    descriptor,
                    timestamp_seconds,
                )
                accepted_threshold, uncertain_threshold, margin_threshold = _thresholds(entity_type)
                best_score, best_identity = matches[0] if matches else (0.0, None)
                margin = best_score - (matches[1][0] if len(matches) > 1 else 0.0)
                if (
                    best_identity is not None
                    and best_score >= accepted_threshold
                    and margin >= margin_threshold
                ):
                    identity = best_identity
                    identity.appearance_count += 1
                    identity.first_seen_timestamp = min(identity.first_seen_timestamp, timestamp_seconds)
                    identity.last_seen_timestamp = max(identity.last_seen_timestamp, timestamp_seconds)
                    identity.appearance_descriptor = _blend_descriptor(
                        identity.appearance_descriptor,
                        descriptor,
                        identity.descriptor_sample_count,
                        1 if descriptor else 0,
                    )
                    identity.descriptor_sample_count += 1 if descriptor else 0
                    identity.matching_confidence = best_score
                    if identity.status != "confirmed":
                        identity.status = "probable"
                    explanation = (
                        f"Track T{track_id:03d} matched {identity.identity_code} with "
                        f"appearance similarity {best_score:.2f}; this is not proof of identity."
                    )
                    association_status = "probable"
                    match_confidence: float | None = best_score
                    candidate_code = None
                else:
                    candidate_code = (
                        best_identity.identity_code
                        if best_identity is not None and best_score >= uncertain_threshold
                        else None
                    )
                    if descriptor is None:
                        explanation = (
                            "Appearance evidence was too small or unavailable; the track remains "
                            "an unresolved source-local identity."
                        )
                    elif candidate_code:
                        explanation = (
                            f"Similarity {best_score:.2f} was uncertain or ambiguous; no merge "
                            "was made."
                        )
                    elif best_identity is None:
                        explanation = (
                            "No earlier non-overlapping identity in this session was available "
                            "for comparison."
                        )
                    else:
                        explanation = (
                            f"No earlier identity met the configured threshold "
                            f"(best similarity {best_score:.2f}); a separate ID was retained."
                        )
                    identity_number = next_identity_numbers.get(entity_type)
                    if identity_number is None:
                        next_code = _next_identity_code(
                            db,
                            "live_session",
                            session_id,
                            entity_type,
                        )
                        identity_number = int(next_code[1:])
                    next_identity_numbers[entity_type] = identity_number + 1
                    identity = _make_identity(
                        user_id=user_id,
                        source_type="live_session",
                        source_id=session_id,
                        analysis_id=None,
                        live_session_id=session_id,
                        identity_code=(
                            f"{'P' if entity_type == 'person' else 'O'}"
                            f"{identity_number:03d}"
                        ),
                        entity_type=entity_type,
                        category=category,
                        first_seen_timestamp=timestamp_seconds,
                        last_seen_timestamp=timestamp_seconds,
                        descriptor=descriptor,
                        descriptor_sample_count=1 if descriptor else 0,
                        matching_confidence=best_score if best_identity else None,
                        candidate_code=candidate_code,
                        matching_explanation=explanation,
                    )
                    db.add(identity)
                    association_status = "unknown"
                    match_confidence = best_score if best_identity else None
                association = _make_track_association(
                    identity=identity,
                    source_type="live_session",
                    source_id=session_id,
                    track_id=int(track_id),
                    category=category,
                    first_seen_timestamp=timestamp_seconds,
                    last_seen_timestamp=timestamp_seconds,
                    detection_count=1,
                    descriptor=descriptor,
                    descriptor_sample_count=1 if descriptor else 0,
                    match_confidence=match_confidence,
                    status=association_status,
                    explanation=explanation,
                    candidate_code=candidate_code,
                    evidence_reference=evidence_reference,
                )
                db.add(association)
            else:
                identity = association.identity
                association.detection_count += 1
                association.last_seen_timestamp = max(
                    association.last_seen_timestamp,
                    timestamp_seconds,
                )
                if descriptor is not None:
                    association.appearance_descriptor = _blend_descriptor(
                        association.appearance_descriptor,
                        descriptor,
                        association.descriptor_sample_count,
                        1,
                    )
                    association.descriptor_sample_count += 1
                    identity.appearance_descriptor = _blend_descriptor(
                        identity.appearance_descriptor,
                        descriptor,
                        identity.descriptor_sample_count,
                        1,
                    )
                    identity.descriptor_sample_count += 1
                if evidence_reference and not association.evidence_reference:
                    association.evidence_reference = evidence_reference
                    identity.evidence_refs = list(
                        dict.fromkeys([*identity.evidence_refs, evidence_reference])
                    )
                identity.last_seen_timestamp = max(identity.last_seen_timestamp, timestamp_seconds)
                _try_upgrade_live_association(db, association)
                identity = association.identity
            identity_codes[int(track_id)] = identity.identity_code
        db.flush()
        return identity_codes


def correct_track_identity(
    db: Session,
    *,
    identity: EntityIdentity,
    association: IdentityTrackAssociation,
    user_id: int,
    target_identity: EntityIdentity | None = None,
    create_new_identity: bool = False,
    correction_note: str | None = None,
) -> EntityIdentity:
    """Manually reassign one source-scoped tracker fragment while retaining its T-ID."""
    if target_identity is None and not create_new_identity:
        raise ValueError("Choose an existing identity or request a new identity.")
    if target_identity is not None and create_new_identity:
        raise ValueError("Choose either an existing identity or a new identity, not both.")
    if target_identity is not None and (
        target_identity.source_type != identity.source_type
        or target_identity.source_id != identity.source_id
        or target_identity.entity_type != identity.entity_type
        or target_identity.user_id != user_id
    ):
        raise ValueError("Target identity must belong to the same user, source, and entity type.")

    with _identity_lock:
        original_identity = association.identity
        if create_new_identity:
            new_identity = _make_identity(
                user_id=user_id,
                source_type=identity.source_type,  # type: ignore[arg-type]
                source_id=identity.source_id,
                analysis_id=identity.analysis_id,
                live_session_id=identity.live_session_id,
                identity_code=_next_identity_code(
                    db,
                    identity.source_type,  # type: ignore[arg-type]
                    identity.source_id,
                    identity.entity_type,
                ),
                entity_type=identity.entity_type,
                category=association.category,
                first_seen_timestamp=association.first_seen_timestamp,
                last_seen_timestamp=association.last_seen_timestamp,
                descriptor=association.appearance_descriptor,
                descriptor_sample_count=association.descriptor_sample_count,
                matching_confidence=1.0,
                candidate_code=None,
                matching_explanation="Identity manually separated by the source owner.",
            )
            new_identity.status = "confirmed"
            db.add(new_identity)
            target_identity = new_identity

        assert target_identity is not None
        association.identity = target_identity
        association.match_status = "confirmed"
        association.match_confidence = 1.0
        association.unresolved_candidate_code = None
        association.manually_corrected = True
        association.corrected_by_user_id = user_id
        association.correction_note = correction_note
        association.matching_explanation = (
            f"Track T{association.track_id:03d} was manually assigned to "
            f"{target_identity.identity_code} by the source owner."
        )
        target_identity.status = "confirmed"
        target_identity.matching_confidence = 1.0
        target_identity.matching_explanation = association.matching_explanation
        db.flush()
        _rebuild_identity_aggregate(db, target_identity)
        if original_identity.id != target_identity.id:
            _rebuild_identity_aggregate(db, original_identity)
            if original_identity.appearance_count == 0:
                original_identity.merged_into_identity_id = target_identity.id
                original_identity.matching_explanation = (
                    f"This identity was manually merged into {target_identity.identity_code}."
                )
        db.flush()
        return target_identity
