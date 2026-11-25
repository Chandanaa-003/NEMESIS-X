from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import uuid


@dataclass(frozen=True)
class ZoneEventDraft:
    id: str
    event_type: str
    category: str
    title: str
    description: str
    start_timestamp: float
    end_timestamp: float
    involved_track_ids: list[int]
    confidence: float
    severity: str
    evidence_frame_ids: list[int]
    explanation_payload: dict[str, Any]


@dataclass
class _TrackZoneState:
    inside: bool | None = None
    candidate_inside: bool | None = None
    candidate_count: int = 0
    candidate_start_timestamp: float = 0.0
    candidate_start_frame: int = 0
    candidate_confidence_total: float = 0.0
    candidate_confidence_count: int = 0
    entry_timestamp: float = 0.0
    entry_frame: int = 0
    entry_count: int = 0
    confidence_total: float = 0.0
    confidence_count: int = 0
    loitering_emitted: bool = False


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """Return whether a normalized point is inside or on the boundary of a polygon."""
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        cross = (x - previous_x) * (current_y - previous_y) - (
            y - previous_y
        ) * (current_x - previous_x)
        if (
            abs(cross) <= 1e-9
            and min(previous_x, current_x) - 1e-9 <= x <= max(previous_x, current_x) + 1e-9
            and min(previous_y, current_y) - 1e-9 <= y <= max(previous_y, current_y) + 1e-9
        ):
            return True
        if (current_y > y) != (previous_y > y):
            crossing_x = (previous_x - current_x) * (y - current_y) / (
                previous_y - current_y
            ) + current_x
            if x < crossing_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


class ZoneIntelligenceEngine:
    """Stateful, per-source polygon transition detector using tracked observations only."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, int], _TrackZoneState] = {}
        self._last_zone_by_track: dict[int, tuple[str, str]] = {}
        self._last_event_at: dict[tuple[str, str, tuple[int, ...]], float] = {}
        self._group_alerted: set[tuple[str, tuple[int, ...]]] = set()
        self._zone_ids: set[str] = set()
        self._zone_signatures: dict[str, str] = {}

    def reset(self) -> None:
        self._states.clear()
        self._last_zone_by_track.clear()
        self._last_event_at.clear()
        self._group_alerted.clear()
        self._zone_ids.clear()
        self._zone_signatures.clear()

    def process_frame(
        self,
        *,
        zones: list[dict[str, Any]],
        detections: list[dict[str, Any]],
        frame_index: int,
        timestamp_seconds: float,
        frame_width: int,
        frame_height: int,
    ) -> list[ZoneEventDraft]:
        if frame_width <= 0 or frame_height <= 0:
            return []

        zone_ids = {str(zone["id"]) for zone in zones}
        signatures = {
            str(zone["id"]): json.dumps(
                {
                    "name": zone.get("name"),
                    "zone_type": zone.get("zone_type"),
                    "polygon": zone.get("polygon"),
                    "settings": zone.get("settings"),
                },
                sort_keys=True,
            )
            for zone in zones
        }
        reset_zone_ids = (self._zone_ids - zone_ids) | {
            zone_id
            for zone_id, signature in signatures.items()
            if self._zone_signatures.get(zone_id) not in (None, signature)
        }
        if reset_zone_ids:
            self._states = {
                key: value for key, value in self._states.items() if key[0] not in reset_zone_ids
            }
            self._last_event_at = {
                key: value for key, value in self._last_event_at.items() if key[0] not in reset_zone_ids
            }
            self._group_alerted = {
                key for key in self._group_alerted if key[0] not in reset_zone_ids
            }
            self._last_zone_by_track = {
                track_id: value
                for track_id, value in self._last_zone_by_track.items()
                if value[0] not in reset_zone_ids
            }
        self._zone_ids = zone_ids
        self._zone_signatures = signatures

        events: list[ZoneEventDraft] = []
        seen_track_ids: set[int] = set()
        zones = sorted(zones, key=lambda zone: str(zone["id"]))
        for detection in detections:
            raw_track_id = detection.get("track_id")
            bbox = detection.get("bbox") or {}
            if raw_track_id is None or not bbox:
                continue
            track_id = int(raw_track_id)
            seen_track_ids.add(track_id)
            class_name = str(detection.get("class_name", "object")).lower()
            x1 = float(bbox.get("x1", 0))
            y1 = float(bbox.get("y1", 0))
            x2 = float(bbox.get("x2", 0))
            y2 = float(bbox.get("y2", 0))
            point_x = ((x1 + x2) / 2.0) / frame_width
            point_y = (y2 if class_name == "person" else (y1 + y2) / 2.0) / frame_height
            confidence = min(1.0, max(0.0, float(detection.get("confidence", 0.0))))
            for zone in zones:
                zone_id = str(zone["id"])
                state = self._states.setdefault((zone_id, track_id), _TrackZoneState())
                candidate_inside = point_in_polygon(point_x, point_y, zone["polygon"])
                if state.inside is None and not candidate_inside:
                    state.inside = False
                    state.candidate_inside = False
                    state.candidate_count = 0
                    continue
                if state.candidate_inside == candidate_inside:
                    state.candidate_count += 1
                    state.candidate_confidence_total += confidence
                    state.candidate_confidence_count += 1
                else:
                    state.candidate_inside = candidate_inside
                    state.candidate_count = 1
                    state.candidate_start_timestamp = timestamp_seconds
                    state.candidate_start_frame = frame_index
                    state.candidate_confidence_total = confidence
                    state.candidate_confidence_count = 1

                settings = zone.get("settings") or {}
                confirmations = int(settings.get("confirmation_frames", 2))
                if state.candidate_count >= confirmations and state.inside != candidate_inside:
                    state.inside = candidate_inside
                    if candidate_inside:
                        state.entry_timestamp = state.candidate_start_timestamp
                        state.entry_frame = state.candidate_start_frame
                        state.entry_count += 1
                        state.loitering_emitted = False
                        state.confidence_total = state.candidate_confidence_total
                        state.confidence_count = state.candidate_confidence_count
                        events.extend(
                            self._on_entry(
                                zone=zone,
                                track_id=track_id,
                                class_name=class_name,
                                state=state,
                                timestamp_seconds=timestamp_seconds,
                                frame_index=frame_index,
                                confidence=self._candidate_confidence(state, confidence),
                            )
                        )
                    else:
                        events.extend(
                            self._on_exit(
                                zone=zone,
                                track_id=track_id,
                                class_name=class_name,
                                state=state,
                                timestamp_seconds=timestamp_seconds,
                                frame_index=frame_index,
                                confidence=self._candidate_confidence(state, confidence),
                            )
                        )
                elif state.inside and candidate_inside:
                    state.confidence_total += confidence
                    state.confidence_count += 1
                    if class_name == "person" and not state.loitering_emitted:
                        duration = timestamp_seconds - state.entry_timestamp
                        loiter_threshold = float(settings.get("loiter_seconds", 30.0))
                        if duration > loiter_threshold:
                            state.loitering_emitted = True
                            event = self._build_event(
                                    zone=zone,
                                    event_type="zone_loitering",
                                    title=f"Person remained in {zone['name']}",
                                    description=(
                                        f"Person T{track_id:03d} remained inside zone "
                                        f"{zone['name']} for {duration:.1f} seconds. "
                                        "Duration alone does not indicate intent."
                                    ),
                                    start_timestamp=state.entry_timestamp,
                                    end_timestamp=timestamp_seconds,
                                    track_ids=[track_id],
                                    confidence=self._average_confidence(state),
                                    severity="medium",
                                    frame_ids=[state.entry_frame, frame_index],
                                    observed_sequence=[
                                        f"Person T{track_id:03d} entered at {state.entry_timestamp:.2f}s.",
                                        f"Person remained in the zone for {duration:.2f}s, exceeding the {loiter_threshold:.2f}s rule.",
                                    ],
                                    why_flagged=(
                                        f"Confirmed zone occupancy exceeded the configured "
                                        f"{loiter_threshold:.2f}s duration threshold."
                                    ),
                                    timestamp_seconds=timestamp_seconds,
                                )
                            if event is not None:
                                events.append(event)

        for (_, track_id), state in self._states.items():
            if track_id not in seen_track_ids:
                state.candidate_inside = None
                state.candidate_count = 0
                state.candidate_confidence_total = 0.0
                state.candidate_confidence_count = 0

        events.extend(
            self._multiple_people_events(
                zones=zones,
                timestamp_seconds=timestamp_seconds,
                frame_index=frame_index,
            )
        )
        return events

    def _on_entry(
        self,
        *,
        zone: dict[str, Any],
        track_id: int,
        class_name: str,
        state: _TrackZoneState,
        timestamp_seconds: float,
        frame_index: int,
        confidence: float,
    ) -> list[ZoneEventDraft]:
        is_person = class_name == "person"
        zone_type = str(zone["zone_type"])
        event_type = (
            "restricted_zone_entry"
            if is_person and zone_type == "restricted"
            else "person_zone_entry"
            if is_person
            else "object_zone_entry"
        )
        track_label = "Person" if is_person else f"{class_name.title()} object"
        entry_event = self._build_event(
                zone=zone,
                event_type=event_type,
                title=f"{track_label} entered {zone['name']}",
                description=f"{track_label} T{track_id:03d} entered the {zone_type} zone {zone['name']}.",
                start_timestamp=state.candidate_start_timestamp,
                end_timestamp=timestamp_seconds,
                track_ids=[track_id],
                confidence=confidence,
                severity="high" if zone_type == "restricted" and is_person else "low",
                frame_ids=[state.candidate_start_frame, frame_index],
                observed_sequence=[
                    f"Track T{track_id:03d} was observed inside zone {zone['name']} for the configured confirmation frames.",
                ],
                why_flagged=(
                    f"Tracked {class_name} crossed into the configured {zone_type} polygon "
                    f"after {zone.get('settings', {}).get('confirmation_frames', 2)} confirmed observations."
                ),
                timestamp_seconds=timestamp_seconds,
            )
        events = [entry_event] if entry_event is not None else []
        if is_person:
            prior = self._last_zone_by_track.get(track_id)
            if prior is not None and prior[0] != str(zone["id"]):
                previous_zone_id, previous_zone_name = prior
                transition_event = self._build_event(
                        zone=zone,
                        event_type="zone_transition",
                        title=f"Person moved between {previous_zone_name} and {zone['name']}",
                        description=(
                            f"Person T{track_id:03d} was observed leaving zone "
                            f"{previous_zone_name} and entering zone {zone['name']}."
                        ),
                        start_timestamp=state.candidate_start_timestamp,
                        end_timestamp=timestamp_seconds,
                        track_ids=[track_id],
                        confidence=confidence,
                        severity="low",
                        frame_ids=[state.candidate_start_frame, frame_index],
                        observed_sequence=[
                            f"Track T{track_id:03d} last exited zone {previous_zone_name}.",
                            f"Track T{track_id:03d} entered zone {zone['name']}.",
                        ],
                        why_flagged="A confirmed track moved from one configured polygon zone to another.",
                        timestamp_seconds=timestamp_seconds,
                        extra_payload={"from_zone_id": previous_zone_id, "from_zone_name": previous_zone_name},
                    )
                if transition_event is not None:
                    events.append(transition_event)
            self._last_zone_by_track[track_id] = (str(zone["id"]), str(zone["name"]))

            if state.entry_count >= 2:
                repeated_event = self._build_event(
                        zone=zone,
                        event_type="repeated_zone_entry",
                        title=f"Repeated entry into {zone['name']}",
                        description=(
                            f"Person T{track_id:03d} has entered zone {zone['name']} "
                            f"{state.entry_count} times."
                        ),
                        start_timestamp=state.entry_timestamp,
                        end_timestamp=timestamp_seconds,
                        track_ids=[track_id],
                        confidence=confidence,
                        severity="medium",
                        frame_ids=[state.entry_frame, frame_index],
                        observed_sequence=[
                            f"Person T{track_id:03d} has entered and exited zone {zone['name']} repeatedly.",
                        ],
                        why_flagged=f"At least two confirmed entries were observed for this track and zone.",
                        timestamp_seconds=timestamp_seconds,
                    )
                if repeated_event is not None:
                    events.append(repeated_event)
        return events

    def _on_exit(
        self,
        *,
        zone: dict[str, Any],
        track_id: int,
        class_name: str,
        state: _TrackZoneState,
        timestamp_seconds: float,
        frame_index: int,
        confidence: float,
    ) -> list[ZoneEventDraft]:
        is_person = class_name == "person"
        track_label = "Person" if is_person else f"{class_name.title()} object"
        event_type = "person_zone_exit" if is_person else "object_zone_exit"
        if is_person:
            self._last_zone_by_track[track_id] = (str(zone["id"]), str(zone["name"]))
        event = self._build_event(
                zone=zone,
                event_type=event_type,
                title=f"{track_label} exited {zone['name']}",
                description=f"{track_label} T{track_id:03d} exited the zone {zone['name']}.",
                start_timestamp=timestamp_seconds,
                end_timestamp=timestamp_seconds,
                track_ids=[track_id],
                confidence=confidence,
                severity="low",
                frame_ids=[frame_index],
                observed_sequence=[
                    f"Track T{track_id:03d} was observed outside zone {zone['name']} for the configured confirmation frames.",
                ],
                why_flagged="A confirmed tracked observation crossed outside the configured zone polygon.",
                timestamp_seconds=timestamp_seconds,
                extra_payload={"entry_timestamp": state.entry_timestamp},
            )
        return [event] if event is not None else []

    def _multiple_people_events(
        self,
        *,
        zones: list[dict[str, Any]],
        timestamp_seconds: float,
        frame_index: int,
    ) -> list[ZoneEventDraft]:
        events: list[ZoneEventDraft] = []
        for zone in zones:
            zone_id = str(zone["id"])
            if zone.get("zone_type") != "restricted":
                continue
            people = sorted(
                track_id
                for (state_zone_id, track_id), state in self._states.items()
                if state_zone_id == zone_id and state.inside
            )
            threshold = int((zone.get("settings") or {}).get("restricted_group_threshold", 2))
            group_key = (zone_id, tuple(people))
            self._group_alerted = {
                key for key in self._group_alerted if key[0] != zone_id or key[1] == tuple(people)
            }
            if len(people) < threshold or group_key in self._group_alerted:
                continue
            self._group_alerted.add(group_key)
            event = self._build_event(
                    zone=zone,
                    event_type="multiple_people_restricted_zone",
                    title=f"Multiple people in restricted zone {zone['name']}",
                    description=(
                        f"{len(people)} people were confirmed inside restricted zone "
                        f"{zone['name']} (configured threshold: {threshold})."
                    ),
                    start_timestamp=timestamp_seconds,
                    end_timestamp=timestamp_seconds,
                    track_ids=people,
                    confidence=sum(
                        self._average_confidence(self._states[(zone_id, track_id)])
                        for track_id in people
                    )
                    / len(people),
                    severity="high",
                    frame_ids=[frame_index],
                    observed_sequence=[
                        f"Tracks {', '.join(f'T{track_id:03d}' for track_id in people)} were concurrently confirmed inside restricted zone {zone['name']}."
                    ],
                    why_flagged=f"The confirmed in-zone person count reached the configured threshold of {threshold}.",
                    timestamp_seconds=timestamp_seconds,
                    extra_payload={"person_count": len(people), "threshold": threshold},
                )
            if event is not None:
                events.append(event)
        return events

    def _build_event(
        self,
        *,
        zone: dict[str, Any],
        event_type: str,
        title: str,
        description: str,
        start_timestamp: float,
        end_timestamp: float,
        track_ids: list[int],
        confidence: float,
        severity: str,
        frame_ids: list[int],
        observed_sequence: list[str],
        why_flagged: str,
        timestamp_seconds: float,
        extra_payload: dict[str, Any] | None = None,
    ) -> ZoneEventDraft | None:
        zone_id = str(zone["id"])
        normalized_track_ids = tuple(sorted(set(track_ids)))
        key = (zone_id, event_type, normalized_track_ids)
        cooldown = float((zone.get("settings") or {}).get("cooldown_seconds", 10.0))
        previous_timestamp = self._last_event_at.get(key)
        if previous_timestamp is not None and timestamp_seconds - previous_timestamp < cooldown:
            return None
        self._last_event_at[key] = timestamp_seconds
        payload: dict[str, Any] = {
            "zone_id": zone_id,
            "zone_name": str(zone["name"]),
            "zone_type": str(zone["zone_type"]),
            "duration_seconds": round(max(0.0, end_timestamp - start_timestamp), 3),
            "observed_sequence": observed_sequence,
            "why_flagged": why_flagged,
            "evidence_timestamps": [round(start_timestamp, 3), round(end_timestamp, 3)],
            "confidence_note": "Rule-based polygon transition confirmed across configured consecutive tracked observations.",
            "requires_human_review": False,
            "alerts_enabled": bool((zone.get("settings") or {}).get("alerts_enabled", True)),
            "voice_alerts_enabled": bool(
                (zone.get("settings") or {}).get("voice_alerts_enabled", True)
            ),
        }
        if extra_payload:
            payload.update(extra_payload)
        return ZoneEventDraft(
            id=str(uuid.uuid4()),
            event_type=event_type,
            category=(
                "other_activities" if event_type.startswith("object_") else "people_movement"
            ),
            title=title,
            description=description,
            start_timestamp=round(start_timestamp, 3),
            end_timestamp=round(max(start_timestamp, end_timestamp), 3),
            involved_track_ids=list(normalized_track_ids),
            confidence=round(min(0.99, max(0.35, confidence)), 3),
            severity=severity,
            evidence_frame_ids=sorted(set(frame_ids)),
            explanation_payload=payload,
        )

    @staticmethod
    def _average_confidence(state: _TrackZoneState) -> float:
        return state.confidence_total / max(state.confidence_count, 1)

    @staticmethod
    def _candidate_confidence(state: _TrackZoneState, fallback: float) -> float:
        return state.candidate_confidence_total / max(state.candidate_confidence_count, 1) or fallback


def discover_recorded_zone_events(
    *,
    detections_path: Path,
    zones: list[dict[str, Any]],
) -> list[ZoneEventDraft]:
    """Analyze sampled detections in timestamp order for saved polygon zones."""
    if not zones or not detections_path.is_file():
        return []
    try:
        raw_data = json.loads(detections_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Failed to read tracked detections for zone analysis.") from exc

    engine = ZoneIntelligenceEngine()
    discovered: list[ZoneEventDraft] = []
    for frame in sorted(raw_data.get("frames", []), key=lambda item: int(item.get("frame_index", 0))):
        frame_width = int(frame.get("frame_width") or 0)
        frame_height = int(frame.get("frame_height") or 0)
        discovered.extend(
            engine.process_frame(
                zones=zones,
                detections=list(frame.get("detections", [])),
                frame_index=int(frame["frame_index"]),
                timestamp_seconds=float(frame["timestamp_seconds"]),
                frame_width=frame_width,
                frame_height=frame_height,
            )
        )
    return discovered


def summarize_zone_events(
    *,
    source_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    event_types: Counter[str] = Counter()
    zones: dict[str, dict[str, Any]] = {}
    for event in events:
        event_types[str(event["event_type"])] += 1
        zone_id = str(event["zone_id"])
        if zone_id not in zones:
            zones[zone_id] = {
                "zone_id": zone_id,
                "zone_name": str(event["zone_name"]),
                "event_count": 0,
                "people_tracks": set(),
                "last_event_timestamp": 0.0,
            }
        summary = zones[zone_id]
        summary["event_count"] += 1
        summary["people_tracks"].update(int(track_id) for track_id in event["involved_track_ids"])
        summary["last_event_timestamp"] = max(
            summary["last_event_timestamp"], float(event["end_timestamp"])
        )
    zone_summaries = [
        {
            **summary,
            "people_tracks": sorted(summary["people_tracks"]),
        }
        for summary in sorted(zones.values(), key=lambda item: item["zone_name"].lower())
    ]
    return {
        "source_id": source_id,
        "total_events": len(events),
        "events_by_type": dict(event_types),
        "zones": zone_summaries,
    }
