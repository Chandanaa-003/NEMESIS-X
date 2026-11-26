from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import uuid
from typing import Any, Literal

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models.identity import EntityIdentity, IdentityObservation

IdentitySourceType = Literal["analysis", "live_session"]
IdentityEntityType = Literal["person", "object"]
IdentityStatus = Literal["confirmed", "probable", "unknown"]
Signature = dict[str, Any]

_FEATURE_REFERENCE = "hsv_color_shape_v1"
_PERSON_CROP_QUALITY = 0.20
_PERSON_DISTINCTIVENESS = 0.12
_OBJECT_CROP_QUALITY = 0.25
_OBJECT_DISTINCTIVENESS = 0.22


@dataclass
class IdentityProfile:
    id: str
    identity_code: str
    entity_type: IdentityEntityType
    class_name: str
    status: IdentityStatus
    first_seen_timestamp: float
    last_seen_timestamp: float
    appearance_count: int
    associated_track_ids: list[int]
    appearance_signature: Signature | None
    last_position: dict[str, float] | None
    matching_confidence: float
    matching_explanation: str
    evidence_refs: list[str] = field(default_factory=list)
    track_intervals: dict[int, tuple[float, float]] = field(default_factory=dict)
    is_new: bool = False


@dataclass(frozen=True)
class IdentityAssignment:
    profile: IdentityProfile
    match_confidence: float
    explanation: str
    is_new_identity: bool
    is_new_track: bool


def _entity_type(class_name: str) -> IdentityEntityType:
    return "person" if class_name.strip().lower() == "person" else "object"


def extract_appearance_signature(
    frame: np.ndarray,
    bbox: dict[str, float] | Any,
    class_name: str,
) -> Signature | None:
    """Build a CPU-only clothing/object color and shape descriptor; no face features are used."""
    if frame is None or frame.ndim != 3 or frame.size == 0:
        return None
    height, width = frame.shape[:2]
    try:
        x1 = max(0, min(width, int(math.floor(float(bbox["x1"] if isinstance(bbox, dict) else bbox.x1)))))
        y1 = max(0, min(height, int(math.floor(float(bbox["y1"] if isinstance(bbox, dict) else bbox.y1)))))
        x2 = max(0, min(width, int(math.ceil(float(bbox["x2"] if isinstance(bbox, dict) else bbox.x2)))))
        y2 = max(0, min(height, int(math.ceil(float(bbox["y2"] if isinstance(bbox, dict) else bbox.y2)))))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None

    box_width = x2 - x1
    box_height = y2 - y1
    if _entity_type(class_name) == "person":
        x1 += int(box_width * 0.12)
        x2 -= int(box_width * 0.12)
        y1 += int(box_height * 0.22)
        y2 -= int(box_height * 0.05)
    crop = frame[y1:y2, x1:x2]
    crop_height, crop_width = crop.shape[:2]
    if crop_width < 12 or crop_height < 12:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [8, 4], [0, 180, 0, 256]).reshape(-1)
    histogram_sum = float(histogram.sum())
    if histogram_sum <= 0:
        return None
    normalized_histogram = histogram.astype(np.float32) / histogram_sum
    nonzero = normalized_histogram[normalized_histogram > 0]
    entropy = float(-(nonzero * np.log(nonzero)).sum() / math.log(len(normalized_histogram)))

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    crop_area = crop_width * crop_height
    size_quality = min(1.0, math.sqrt(crop_area / float(48 * 48)))
    quality = min(1.0, size_quality * min(1.0, sharpness / 30.0))

    return {
        "histogram": [round(float(value), 6) for value in normalized_histogram],
        "aspect_ratio": round(float(crop_width / max(crop_height, 1)), 4),
        "quality": round(quality, 4),
        "distinctiveness": round(max(0.0, min(1.0, entropy)), 4),
    }


def aggregate_signatures(signatures: list[Signature]) -> Signature | None:
    usable = [
        signature
        for signature in signatures
        if isinstance(signature.get("histogram"), list)
        and len(signature["histogram"]) == 32
        and float(signature.get("quality", 0.0)) > 0
    ]
    if not usable:
        return None
    weights = np.asarray([float(item["quality"]) for item in usable], dtype=np.float32)
    histograms = np.asarray([item["histogram"] for item in usable], dtype=np.float32)
    histogram = np.average(histograms, axis=0, weights=weights)
    histogram /= max(float(histogram.sum()), 1e-8)
    return {
        "histogram": [round(float(value), 6) for value in histogram],
        "aspect_ratio": round(
            float(np.average([float(item["aspect_ratio"]) for item in usable], weights=weights)), 4
        ),
        "quality": round(float(np.average([float(item["quality"]) for item in usable], weights=weights)), 4),
        "distinctiveness": round(
            float(np.average([float(item["distinctiveness"]) for item in usable], weights=weights)), 4
        ),
    }


def appearance_similarity(left: Signature, right: Signature) -> float:
    left_hist = np.asarray(left.get("histogram", []), dtype=np.float32)
    right_hist = np.asarray(right.get("histogram", []), dtype=np.float32)
    if left_hist.shape != (32,) or right_hist.shape != (32,):
        return 0.0
    denominator = float(np.linalg.norm(left_hist) * np.linalg.norm(right_hist))
    if denominator <= 0:
        return 0.0
    color_similarity = max(0.0, min(1.0, float(np.dot(left_hist, right_hist) / denominator)))
    left_ratio = max(float(left.get("aspect_ratio", 0.0)), 1e-4)
    right_ratio = max(float(right.get("aspect_ratio", 0.0)), 1e-4)
    shape_similarity = max(0.0, 1.0 - abs(math.log(left_ratio / right_ratio)))
    return round(0.88 * color_similarity + 0.12 * shape_similarity, 4)


def _profile_from_row(row: EntityIdentity, observations: list[IdentityObservation]) -> IdentityProfile:
    return IdentityProfile(
        id=row.id,
        identity_code=row.identity_code,
        entity_type=row.entity_type,  # type: ignore[arg-type]
        class_name=row.class_name,
        status=row.status,  # type: ignore[arg-type]
        first_seen_timestamp=row.first_seen_timestamp,
        last_seen_timestamp=row.last_seen_timestamp,
        appearance_count=row.appearance_count,
        associated_track_ids=list(row.associated_track_ids or []),
        appearance_signature=row.appearance_signature,
        last_position=row.last_position,
        matching_confidence=row.matching_confidence,
        matching_explanation=row.matching_explanation,
        evidence_refs=list(row.evidence_refs or []),
        track_intervals={
            int(item.track_id): (float(item.first_seen_timestamp), float(item.last_seen_timestamp))
            for item in observations
        },
    )


class IdentityMatcher:
    """Source-local conservative matcher; appearance matches are always marked probable."""

    def __init__(
        self,
        source_type: IdentitySourceType,
        source_id: str,
        profiles: list[IdentityProfile] | None = None,
    ) -> None:
        self.source_type = source_type
        self.source_id = source_id
        self.profiles = profiles or []
        self._tracks: dict[int, IdentityProfile] = {
            track_id: profile
            for profile in self.profiles
            for track_id in profile.associated_track_ids
        }

    @classmethod
    def from_database(
        cls,
        db: Session,
        source_type: IdentitySourceType,
        source_id: str,
        user_id: int,
    ) -> IdentityMatcher:
        rows = (
            db.query(EntityIdentity)
            .filter(
                EntityIdentity.user_id == user_id,
                EntityIdentity.source_type == source_type,
                EntityIdentity.source_id == source_id,
            )
            .order_by(EntityIdentity.first_seen_timestamp.asc(), EntityIdentity.identity_code.asc())
            .all()
        )
        observations = (
            db.query(IdentityObservation)
            .filter(
                IdentityObservation.user_id == user_id,
                IdentityObservation.source_type == source_type,
                IdentityObservation.source_id == source_id,
            )
            .all()
        )
        observations_by_identity: dict[str, list[IdentityObservation]] = {}
        for observation in observations:
            observations_by_identity.setdefault(observation.identity_id, []).append(observation)
        return cls(
            source_type,
            source_id,
            [
                _profile_from_row(row, observations_by_identity.get(row.id, []))
                for row in rows
            ],
        )

    def observe_existing_track(self, track_id: int, timestamp: float) -> IdentityProfile | None:
        profile = self._tracks.get(track_id)
        if profile is None:
            return None
        previous = profile.track_intervals.get(track_id)
        if previous is not None:
            profile.track_intervals[track_id] = (previous[0], max(previous[1], timestamp))
        profile.last_seen_timestamp = max(profile.last_seen_timestamp, timestamp)
        return profile

    def assign(
        self,
        *,
        track_id: int,
        class_name: str,
        signature: Signature | None,
        first_seen_timestamp: float,
        last_seen_timestamp: float,
        first_position: dict[str, float] | None = None,
        last_position: dict[str, float] | None = None,
        evidence_ref: str | None = None,
    ) -> IdentityAssignment:
        existing_track = self._tracks.get(track_id)
        if existing_track is not None:
            self.observe_existing_track(track_id, last_seen_timestamp)
            return IdentityAssignment(
                existing_track,
                existing_track.matching_confidence,
                existing_track.matching_explanation,
                False,
                False,
            )

        kind = _entity_type(class_name)
        candidates: list[tuple[float, IdentityProfile]] = []
        enough_feature = signature is not None and self._feature_is_distinctive(signature, kind)
        if enough_feature:
            for profile in self.profiles:
                if profile.entity_type != kind or profile.class_name.lower() != class_name.lower():
                    continue
                if self._has_overlapping_track(profile, first_seen_timestamp, last_seen_timestamp):
                    continue
                if profile.appearance_signature is None:
                    continue
                similarity = appearance_similarity(signature, profile.appearance_signature)
                if kind == "object":
                    if not profile.last_position or not first_position:
                        continue
                    gap = max(0.0, first_seen_timestamp - profile.last_seen_timestamp)
                    tolerance = min(0.65, 0.08 + gap * 0.12)
                    distance = math.hypot(
                        float(profile.last_position["x"]) - float(first_position["x"]),
                        float(profile.last_position["y"]) - float(first_position["y"]),
                    )
                    spatial_score = max(0.0, 1.0 - distance / max(tolerance, 0.08))
                    similarity = 0.90 * similarity + 0.10 * spatial_score
                candidates.append((similarity, profile))
        candidates.sort(key=lambda item: item[0], reverse=True)

        threshold = self._threshold(kind)
        ambiguous_match = False
        if candidates and candidates[0][0] >= threshold:
            best_score, best_profile = candidates[0]
            second_score = candidates[1][0] if len(candidates) > 1 else 0.0
            if best_score - second_score >= get_settings().identity_match_margin:
                best_profile.associated_track_ids.append(track_id)
                best_profile.appearance_count = len(set(best_profile.associated_track_ids))
                best_profile.track_intervals[track_id] = (
                    first_seen_timestamp,
                    last_seen_timestamp,
                )
                best_profile.first_seen_timestamp = min(
                    best_profile.first_seen_timestamp, first_seen_timestamp
                )
                best_profile.last_seen_timestamp = max(
                    best_profile.last_seen_timestamp, last_seen_timestamp
                )
                best_profile.last_position = last_position or best_profile.last_position
                best_profile.matching_confidence = best_score
                best_profile.matching_explanation = (
                    f"Possible appearance match: color/shape similarity {best_score:.2f} "
                    f"meets the configured {threshold:.2f} threshold with a distinct candidate "
                    "margin. No facial features are used; manual review is recommended."
                )
                best_profile.appearance_signature = _blend_signatures(
                    best_profile.appearance_signature, signature
                )
                if evidence_ref:
                    best_profile.evidence_refs.append(evidence_ref)
                self._tracks[track_id] = best_profile
                return IdentityAssignment(
                    best_profile,
                    best_score,
                    best_profile.matching_explanation,
                    False,
                    True,
                )
            explanation = (
                f"Unresolved appearance: the top similarity {best_score:.2f} is too close to "
                f"another candidate ({second_score:.2f}); entities were kept separate."
            )
            confidence = best_score
            ambiguous_match = True
        elif not enough_feature:
            explanation = (
                "Unresolved appearance: the crop is too small, blurry, or visually "
                "non-distinctive for a reliable automatic match."
            )
            confidence = candidates[0][0] if candidates else 0.0
        elif candidates:
            explanation = (
                f"No source-local identity reached the configured {threshold:.2f} "
                f"appearance threshold (best score {candidates[0][0]:.2f})."
            )
            confidence = candidates[0][0]
        else:
            explanation = (
                "No prior non-overlapping source-local identity was a sufficiently distinctive "
                "candidate; a new anonymous label was assigned to this track."
            )
            confidence = 0.0

        profile = self._new_profile(
            kind=kind,
            class_name=class_name,
            signature=signature if enough_feature else None,
            first_seen_timestamp=first_seen_timestamp,
            last_seen_timestamp=last_seen_timestamp,
            last_position=last_position,
            track_id=track_id,
            status="probable" if enough_feature and not ambiguous_match else "unknown",
            confidence=confidence,
            explanation=explanation,
            evidence_ref=evidence_ref,
        )
        self.profiles.append(profile)
        self._tracks[track_id] = profile
        return IdentityAssignment(profile, confidence, explanation, True, True)

    @staticmethod
    def _feature_is_distinctive(signature: Signature, kind: IdentityEntityType) -> bool:
        quality = float(signature.get("quality", 0.0))
        distinctiveness = float(signature.get("distinctiveness", 0.0))
        minimum_quality = _PERSON_CROP_QUALITY if kind == "person" else _OBJECT_CROP_QUALITY
        minimum_distinctiveness = (
            _PERSON_DISTINCTIVENESS if kind == "person" else _OBJECT_DISTINCTIVENESS
        )
        return quality >= minimum_quality and distinctiveness >= minimum_distinctiveness

    @staticmethod
    def _has_overlapping_track(
        profile: IdentityProfile, start: float, end: float
    ) -> bool:
        return any(
            other_start <= end and other_end >= start
            for other_start, other_end in profile.track_intervals.values()
        )

    @staticmethod
    def _threshold(kind: IdentityEntityType) -> float:
        settings = get_settings()
        return (
            settings.identity_person_similarity_threshold
            if kind == "person"
            else settings.identity_object_similarity_threshold
        )

    def _new_profile(
        self,
        *,
        kind: IdentityEntityType,
        class_name: str,
        signature: Signature | None,
        first_seen_timestamp: float,
        last_seen_timestamp: float,
        last_position: dict[str, float] | None,
        track_id: int,
        status: IdentityStatus,
        confidence: float,
        explanation: str,
        evidence_ref: str | None,
    ) -> IdentityProfile:
        prefix = "P" if kind == "person" else "O"
        used_numbers = [
            int(profile.identity_code[1:])
            for profile in self.profiles
            if profile.identity_code.startswith(prefix)
            and profile.identity_code[1:].isdigit()
        ]
        identity_code = f"{prefix}{max(used_numbers, default=0) + 1:03d}"
        return IdentityProfile(
            id=str(uuid.uuid4()),
            identity_code=identity_code,
            entity_type=kind,
            class_name=class_name,
            status=status,
            first_seen_timestamp=first_seen_timestamp,
            last_seen_timestamp=last_seen_timestamp,
            appearance_count=1,
            associated_track_ids=[track_id],
            appearance_signature=signature,
            last_position=last_position,
            matching_confidence=confidence,
            matching_explanation=explanation,
            evidence_refs=[evidence_ref] if evidence_ref else [],
            track_intervals={track_id: (first_seen_timestamp, last_seen_timestamp)},
            is_new=True,
        )


def _blend_signatures(left: Signature | None, right: Signature | None) -> Signature | None:
    if left is None:
        return right
    return aggregate_signatures([left, right])


def save_identity_evidence(
    *,
    source_type: IdentitySourceType,
    source_id: str,
    track_id: int,
    frame: np.ndarray,
    bbox: dict[str, float] | Any,
    class_name: str,
) -> str | None:
    """Store a small anonymous crop; person evidence excludes the head/face region."""
    signature_region = _evidence_crop(frame, bbox, class_name)
    if signature_region is None:
        return None
    if signature_region.shape[1] > 320:
        target_width = 320
        target_height = max(1, round(signature_region.shape[0] * target_width / signature_region.shape[1]))
        signature_region = cv2.resize(
            signature_region, (target_width, target_height), interpolation=cv2.INTER_AREA
        )
    root = get_settings().resolved_identity_evidence_dir
    folder = (root / source_type / Path(source_id).name).resolve()
    if folder.parent.parent != root.resolve():
        raise ValueError("Invalid identity evidence path.")
    folder.mkdir(parents=True, exist_ok=True)
    target = (folder / f"track_{int(track_id)}.jpg").resolve()
    if target.parent != folder:
        raise ValueError("Invalid identity evidence filename.")
    temporary = target.with_suffix(".tmp.jpg")
    if not cv2.imwrite(str(temporary), signature_region, [int(cv2.IMWRITE_JPEG_QUALITY), 75]):
        raise OSError("Unable to save identity appearance evidence.")
    os.replace(temporary, target)
    project_root = BACKEND_DIR.parent.resolve()
    try:
        return target.relative_to(project_root).as_posix()
    except ValueError:
        return str(target)


def _evidence_crop(
    frame: np.ndarray, bbox: dict[str, float] | Any, class_name: str
) -> np.ndarray | None:
    if frame is None or frame.ndim != 3:
        return None
    height, width = frame.shape[:2]
    try:
        x1 = int(max(0, min(width, float(bbox["x1"] if isinstance(bbox, dict) else bbox.x1))))
        y1 = int(max(0, min(height, float(bbox["y1"] if isinstance(bbox, dict) else bbox.y1))))
        x2 = int(max(0, min(width, float(bbox["x2"] if isinstance(bbox, dict) else bbox.x2))))
        y2 = int(max(0, min(height, float(bbox["y2"] if isinstance(bbox, dict) else bbox.y2))))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    if _entity_type(class_name) == "person":
        y1 += int((y2 - y1) * 0.22)
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def _persist_profile(db: Session, user_id: int, source_type: IdentitySourceType, source_id: str, profile: IdentityProfile) -> EntityIdentity:
    row = db.query(EntityIdentity).filter(EntityIdentity.id == profile.id).first()
    if row is None:
        row = EntityIdentity(
            id=profile.id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            analysis_id=source_id if source_type == "analysis" else None,
            live_session_id=source_id if source_type == "live_session" else None,
            identity_code=profile.identity_code,
            entity_type=profile.entity_type,
            category=profile.class_name,
            class_name=profile.class_name,
            status=profile.status,
            first_seen_timestamp=profile.first_seen_timestamp,
            last_seen_timestamp=profile.last_seen_timestamp,
            appearance_count=profile.appearance_count,
            descriptor_sample_count=1 if profile.appearance_signature else 0,
            associated_track_ids=sorted(set(profile.associated_track_ids)),
            appearance_descriptor=profile.appearance_signature,
            appearance_signature=profile.appearance_signature,
            feature_reference=_FEATURE_REFERENCE,
            matching_confidence=profile.matching_confidence,
            matching_explanation=profile.matching_explanation,
            evidence_refs=sorted(set(profile.evidence_refs)),
        )
        db.add(row)
        db.flush()
        profile.is_new = False
        return row
    row.status = profile.status
    row.first_seen_timestamp = profile.first_seen_timestamp
    row.last_seen_timestamp = profile.last_seen_timestamp
    row.appearance_count = profile.appearance_count
    row.associated_track_ids = sorted(set(profile.associated_track_ids))
    row.category = profile.class_name
    row.descriptor_sample_count = max(
        row.descriptor_sample_count,
        1 if profile.appearance_signature else 0,
    )
    row.appearance_descriptor = profile.appearance_signature
    row.appearance_signature = profile.appearance_signature
    row.last_position = profile.last_position
    row.matching_confidence = profile.matching_confidence
    row.matching_explanation = profile.matching_explanation
    row.evidence_refs = sorted(set(profile.evidence_refs))
    db.flush()
    return row


def _persist_observation(
    db: Session,
    *,
    user_id: int,
    source_type: IdentitySourceType,
    source_id: str,
    track_id: int,
    class_name: str,
    first_seen_timestamp: float,
    last_seen_timestamp: float,
    detection_count: int,
    match_confidence: float,
    feature_quality: float,
    matching_explanation: str,
    bbox: dict[str, float] | None,
    evidence_path: str | None,
    appearance_signature: Signature | None,
    last_position: dict[str, float] | None,
    identity_id: str,
) -> IdentityObservation:
    observation = (
        db.query(IdentityObservation)
        .filter(
            IdentityObservation.source_type == source_type,
            IdentityObservation.source_id == source_id,
            IdentityObservation.track_id == track_id,
        )
        .first()
    )
    if observation is None:
        observation = IdentityObservation(
            identity_id=identity_id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            track_id=track_id,
            class_name=class_name,
            first_seen_timestamp=first_seen_timestamp,
            last_seen_timestamp=last_seen_timestamp,
            detection_count=detection_count,
            match_confidence=match_confidence,
            feature_quality=feature_quality,
            matching_explanation=matching_explanation,
            bbox=bbox,
            evidence_path=evidence_path,
            appearance_signature=appearance_signature,
            last_position=last_position,
        )
        db.add(observation)
    else:
        observation.first_seen_timestamp = min(observation.first_seen_timestamp, first_seen_timestamp)
        observation.last_seen_timestamp = max(observation.last_seen_timestamp, last_seen_timestamp)
        observation.detection_count = max(observation.detection_count, detection_count)
        observation.match_confidence = match_confidence
        observation.feature_quality = max(observation.feature_quality, feature_quality)
        observation.matching_explanation = matching_explanation
        observation.bbox = bbox or observation.bbox
        observation.evidence_path = evidence_path or observation.evidence_path
        observation.appearance_signature = appearance_signature or observation.appearance_signature
        observation.last_position = last_position or observation.last_position
    db.flush()
    return observation


def _set_observation_identity(
    observation: IdentityObservation, profile: IdentityProfile
) -> None:
    observation.identity_id = profile.id


def _bbox_from_detection(detection: dict[str, Any]) -> dict[str, float] | None:
    bbox = detection.get("bbox")
    if not isinstance(bbox, dict):
        return None
    try:
        return {key: float(bbox[key]) for key in ("x1", "y1", "x2", "y2")}
    except (KeyError, TypeError, ValueError):
        return None


def recognize_recorded_analysis(
    *,
    db: Session,
    analysis_id: str,
    user_id: int,
    analysis_dir: Path,
) -> dict[str, Any]:
    """Create source-local identities from stored chronological detections and frame crops."""
    detections_path = analysis_dir / "detections.json"
    tracks_path = analysis_dir / "tracks.json"
    frames_dir = (analysis_dir / "frames").resolve()
    if not detections_path.is_file() or not tracks_path.is_file():
        raise FileNotFoundError("Recorded identity matching requires detections.json and tracks.json.")
    try:
        detections_data = json.loads(detections_path.read_text(encoding="utf-8"))
        tracks_data = json.loads(tracks_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Recorded identity tracking data could not be read.") from exc

    db.query(IdentityObservation).filter(
        IdentityObservation.source_type == "analysis",
        IdentityObservation.source_id == analysis_id,
    ).delete(synchronize_session=False)
    db.query(EntityIdentity).filter(
        EntityIdentity.source_type == "analysis",
        EntityIdentity.source_id == analysis_id,
    ).delete(synchronize_session=False)

    grouped: dict[int, dict[str, Any]] = {}
    frame_entries = sorted(
        detections_data.get("frames", []), key=lambda item: float(item.get("timestamp_seconds", 0))
    )
    for frame_entry in frame_entries:
        filename = str(frame_entry.get("filename", ""))
        frame_path = (frames_dir / Path(filename).name).resolve()
        if frame_path.parent != frames_dir or not frame_path.is_file():
            continue
        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue
        timestamp = float(frame_entry.get("timestamp_seconds", 0.0))
        frame_index = int(frame_entry.get("frame_index", 0))
        for detection in frame_entry.get("detections", []):
            raw_track_id = detection.get("track_id")
            bbox = _bbox_from_detection(detection)
            if raw_track_id is None or bbox is None:
                continue
            track_id = int(raw_track_id)
            class_name = str(detection.get("class_name", "object"))
            signature = extract_appearance_signature(frame, bbox, class_name)
            item = grouped.setdefault(
                track_id,
                {
                    "class_name": class_name,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "detection_count": 0,
                    "samples": [],
                    "best_sample": None,
                    "first_position": None,
                    "last_position": None,
                },
            )
            frame_width = int(frame_entry.get("frame_width") or frame.shape[1])
            frame_height = int(frame_entry.get("frame_height") or frame.shape[0])
            center = {
                "x": round((bbox["x1"] + bbox["x2"]) / (2 * max(frame_width, 1)), 4),
                "y": round((bbox["y1"] + bbox["y2"]) / (2 * max(frame_height, 1)), 4),
            }
            if item["first_position"] is None:
                item["first_position"] = center
            item["last_position"] = center
            item["first_seen"] = min(item["first_seen"], timestamp)
            item["last_seen"] = max(item["last_seen"], timestamp)
            item["detection_count"] += 1
            if signature is not None:
                samples: list[Signature] = item["samples"]
                if len(samples) < 12 and (not samples or frame_index % 5 == 0):
                    samples.append(signature)
                best = item["best_sample"]
                if best is None or signature["quality"] > best["signature"]["quality"]:
                    item["best_sample"] = {
                        "signature": signature,
                        "frame_path": frame_path,
                        "bbox": bbox,
                        "frame_index": frame_index,
                    }

    matcher = IdentityMatcher("analysis", analysis_id)
    assignment_by_track: dict[int, IdentityAssignment] = {}
    for track_id, item in sorted(
        grouped.items(), key=lambda entry: (entry[1]["first_seen"], entry[0])
    ):
        signature = aggregate_signatures(item["samples"])
        best_sample = item["best_sample"]
        evidence_path = None
        if best_sample is not None and best_sample["signature"]["quality"] >= 0.20:
            best_frame = cv2.imread(str(best_sample["frame_path"]))
            if best_frame is None:
                raise OSError("Could not load the selected identity evidence frame.")
            evidence_path = save_identity_evidence(
                source_type="analysis",
                source_id=analysis_id,
                track_id=track_id,
                frame=best_frame,
                bbox=best_sample["bbox"],
                class_name=item["class_name"],
            )
        assignment = matcher.assign(
            track_id=track_id,
            class_name=item["class_name"],
            signature=signature,
            first_seen_timestamp=float(item["first_seen"]),
            last_seen_timestamp=float(item["last_seen"]),
            first_position=item["first_position"],
            last_position=item["last_position"],
            evidence_ref=None,
        )
        profile = assignment.profile
        evidence_ref = (
            f"{get_settings().api_v1_prefix}/identities/"
            f"{profile.id}/observations/{track_id}/evidence"
            if evidence_path
            else None
        )
        if evidence_ref and evidence_ref not in profile.evidence_refs:
            profile.evidence_refs.append(evidence_ref)
        identity_row = _persist_profile(db, user_id, "analysis", analysis_id, profile)
        observation = _persist_observation(
            db,
            user_id=user_id,
            source_type="analysis",
            source_id=analysis_id,
            track_id=track_id,
            class_name=item["class_name"],
            first_seen_timestamp=float(item["first_seen"]),
            last_seen_timestamp=float(item["last_seen"]),
            detection_count=int(item["detection_count"]),
            match_confidence=assignment.match_confidence,
            feature_quality=float((signature or {}).get("quality", 0.0)),
            matching_explanation=assignment.explanation,
            bbox=best_sample["bbox"] if best_sample else None,
            evidence_path=evidence_path,
            appearance_signature=signature,
            last_position=item["last_position"],
            identity_id=profile.id,
        )
        _set_observation_identity(observation, profile)
        identity_row.evidence_refs = sorted(set(profile.evidence_refs))
        assignment_by_track[track_id] = assignment

    for frame_entry in detections_data.get("frames", []):
        for detection in frame_entry.get("detections", []):
            track_id = detection.get("track_id")
            assignment = assignment_by_track.get(int(track_id)) if track_id is not None else None
            if assignment:
                detection.update(
                    {
                        "identity_id": assignment.profile.id,
                        "identity_code": assignment.profile.identity_code,
                        "identity_status": assignment.profile.status,
                        "identity_confidence": assignment.match_confidence,
                    }
                )
    for track in tracks_data.get("tracks", []):
        assignment = assignment_by_track.get(int(track.get("track_id", -1)))
        if assignment:
            track.update(
                {
                    "identity_id": assignment.profile.id,
                    "identity_code": assignment.profile.identity_code,
                    "identity_status": assignment.profile.status,
                    "identity_confidence": assignment.match_confidence,
                }
            )

    _write_json_atomically(detections_path, detections_data)
    _write_json_atomically(tracks_path, tracks_data)
    db.commit()
    return {
        "total_unique_people": sum(p.entity_type == "person" for p in matcher.profiles),
        "total_unique_objects": sum(p.entity_type == "object" for p in matcher.profiles),
        "identity_count": len(matcher.profiles),
    }


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def initialize_live_identity_matcher(
    *, db: Session, session_id: str, user_id: int
) -> IdentityMatcher:
    return IdentityMatcher.from_database(db, "live_session", session_id, user_id)


def identify_live_detections(
    *,
    db: Session,
    matcher: IdentityMatcher,
    session_id: str,
    user_id: int,
    frame: np.ndarray,
    frame_index: int,
    timestamp: float,
    detections: list[Any],
) -> None:
    """Assign labels to tracked live detections and persist one record per track fragment."""
    for detection in detections:
        track_id = detection.track_id
        if track_id is None:
            detection.identity_id = None
            detection.identity_code = None
            detection.identity_status = "unknown"
            detection.identity_confidence = 0.0
            continue
        track_id = int(track_id)
        bbox = detection.bbox.model_dump()
        signature = extract_appearance_signature(frame, bbox, detection.class_name)
        position = {
            "x": round((bbox["x1"] + bbox["x2"]) / (2 * max(frame.shape[1], 1)), 4),
            "y": round((bbox["y1"] + bbox["y2"]) / (2 * max(frame.shape[0], 1)), 4),
        }
        existing_profile = matcher.observe_existing_track(track_id, timestamp)
        if existing_profile is None:
            evidence_path = None
            if signature is not None and signature["quality"] >= 0.20:
                evidence_path = save_identity_evidence(
                    source_type="live_session",
                    source_id=session_id,
                    track_id=track_id,
                    frame=frame,
                    bbox=bbox,
                    class_name=detection.class_name,
                )
            assignment = matcher.assign(
                track_id=track_id,
                class_name=detection.class_name,
                signature=signature,
                first_seen_timestamp=timestamp,
                last_seen_timestamp=timestamp,
                first_position=position,
                last_position=position,
                evidence_ref=None,
            )
            profile = assignment.profile
            evidence_ref = (
                f"{get_settings().api_v1_prefix}/identities/"
                f"{profile.id}/observations/{track_id}/evidence"
                if evidence_path
                else None
            )
            if evidence_ref and evidence_ref not in profile.evidence_refs:
                profile.evidence_refs.append(evidence_ref)
            _persist_profile(db, user_id, "live_session", session_id, profile)
            observation = _persist_observation(
                db,
                user_id=user_id,
                source_type="live_session",
                source_id=session_id,
                track_id=track_id,
                class_name=detection.class_name,
                first_seen_timestamp=timestamp,
                last_seen_timestamp=timestamp,
                detection_count=1,
                match_confidence=assignment.match_confidence,
                feature_quality=float((signature or {}).get("quality", 0.0)),
                matching_explanation=assignment.explanation,
                bbox=bbox,
                evidence_path=evidence_path,
                appearance_signature=signature,
                last_position=position,
                identity_id=profile.id,
            )
            _set_observation_identity(observation, profile)
        else:
            profile = existing_profile
            last_seen_timestamp = max(
                profile.track_intervals.get(track_id, (timestamp, timestamp))[1], timestamp
            )
            db.query(IdentityObservation).filter(
                IdentityObservation.source_type == "live_session",
                IdentityObservation.source_id == session_id,
                IdentityObservation.track_id == track_id,
                IdentityObservation.user_id == user_id,
            ).update(
                {
                    "last_seen_timestamp": last_seen_timestamp,
                    "detection_count": IdentityObservation.detection_count + 1,
                    "bbox": bbox,
                    "last_position": position,
                },
                synchronize_session=False,
            )
            db.query(EntityIdentity).filter(
                EntityIdentity.id == profile.id,
                EntityIdentity.user_id == user_id,
            ).update(
                {
                    "last_seen_timestamp": profile.last_seen_timestamp,
                    "last_position": position,
                },
                synchronize_session=False,
            )
        detection.identity_code = profile.identity_code
        detection.identity_id = profile.id
        detection.identity_status = profile.status
        detection.identity_confidence = profile.matching_confidence


def get_identity_evidence_path(
    *, observation: IdentityObservation, identity: EntityIdentity
) -> Path:
    """Resolve an identity crop only under the configured identity evidence directory."""
    if not observation.evidence_path:
        raise FileNotFoundError("No appearance evidence was retained for this track.")
    project_root = BACKEND_DIR.parent.resolve()
    candidate = Path(observation.evidence_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    root = get_settings().resolved_identity_evidence_dir.resolve()
    expected_parent = (root / identity.source_type / Path(identity.source_id).name).resolve()
    allowed_parents = {expected_parent}
    if identity.source_type == "live_session":
        live_root = get_settings().resolved_live_dir.resolve()
        legacy_parent = (live_root / Path(identity.source_id).name / "identity-evidence").resolve()
        if legacy_parent.parent.parent == live_root:
            allowed_parents.add(legacy_parent)
    if resolved.parent not in allowed_parents:
        raise PermissionError("Identity evidence path is outside the source-scoped evidence directory.")
    if not resolved.is_file():
        raise FileNotFoundError("Identity appearance evidence is no longer available.")
    return resolved