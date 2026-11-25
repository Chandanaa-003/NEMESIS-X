from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class InteractionConfig:
    """Configurable thresholds (in normalized image coordinates and seconds)."""

    proximity_threshold_norm: float = 0.24
    approach_delta_norm: float = 0.05
    departure_delta_norm: float = 0.05
    stationary_displacement_norm: float = 0.04
    stationary_min_seconds: float = 3.0
    stationary_min_frames: int = 3
    unattended_min_seconds: float = 2.0
    unattended_min_frames: int = 2
    repeated_visit_min_cycles: int = 2
    multi_person_proximity_norm: float = 0.28
    multi_person_min_frames: int = 2
    edge_margin_norm: float = 0.14


@dataclass(frozen=True)
class NormalizedTrackPoint:
    """Normalized [0..1] spatial snapshot for a tracked object."""

    frame_index: int
    timestamp_seconds: float
    norm_x: float
    norm_y: float
    confidence: float


@dataclass(frozen=True)
class TrackMotionProfile:
    """Motion and temporal characteristics of one tracked object."""

    track_id: int
    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    duration_seconds: float
    frame_count: int
    avg_confidence: float
    max_displacement_norm: float
    net_displacement_norm: float
    direction_label: str
    is_stationary: bool
    started_near_edge: bool
    ended_near_edge: bool
    points_by_frame: dict[int, NormalizedTrackPoint] = field(default_factory=dict)


@dataclass(frozen=True)
class PairwiseDistancePoint:
    """Normalized center-to-center distance between two tracks at one frame."""

    frame_index: int
    timestamp_seconds: float
    distance_norm: float


@dataclass(frozen=True)
class PersonObjectInteraction:
    """Computed proximity, approach, departure, and visit cycles for a person-object pair."""

    person_track_id: int
    object_track_id: int
    object_class_name: str
    distance_series: list[PairwiseDistancePoint]
    min_distance_norm: float
    min_distance_frame: int
    min_distance_timestamp: float
    approach_window: tuple[int, int, float, float, float, float] | None
    departure_window: tuple[int, int, float, float, float, float] | None
    proximity_visit_windows: list[tuple[int, int, float, float]]


@dataclass(frozen=True)
class PersonPersonInteraction:
    """Computed co-presence proximity between two distinct person tracks."""

    track_id_a: int
    track_id_b: int
    shared_proximity_frames: list[int]
    start_timestamp: float
    end_timestamp: float
    min_distance_norm: float


@dataclass(frozen=True)
class InteractionAnalysisResult:
    """Complete spatial-temporal interaction output across all tracks."""

    frame_width: int
    frame_height: int
    min_frame_index: int
    max_frame_index: int
    track_profiles: dict[int, TrackMotionProfile]
    person_object_interactions: list[PersonObjectInteraction]
    person_person_interactions: list[PersonPersonInteraction]


def _classify_direction(dx: float, dy: float, net_dist: float, stationary_thresh: float) -> str:
    """Describe relative 2D image-plane movement direction without physical distance claims."""
    if net_dist <= stationary_thresh:
        return "mostly stationary"
    horiz = "right" if dx > 0.02 else "left" if dx < -0.02 else ""
    vert = "downward" if dy > 0.02 else "upward" if dy < -0.02 else ""
    if horiz and vert:
        return f"moving {horiz} and {vert}"
    if horiz:
        return f"moving {horiz}"
    if vert:
        return f"moving {vert}"
    return "shifting locally"


def _is_near_edge(nx: float, ny: float, margin: float) -> bool:
    return nx <= margin or nx >= (1.0 - margin) or ny <= margin or ny >= (1.0 - margin)


def analyze_track_interactions(
    *,
    tracks_data: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
    all_frame_indices: list[int],
    config: InteractionConfig | None = None,
) -> InteractionAnalysisResult:
    """Compute normalized motion profiles and pairwise interactions from tracked trajectories."""
    cfg = config or InteractionConfig()
    safe_w = max(frame_width, 1)
    safe_h = max(frame_height, 1)

    min_frame_idx = min(all_frame_indices) if all_frame_indices else 0
    max_frame_idx = max(all_frame_indices) if all_frame_indices else 0

    profiles: dict[int, TrackMotionProfile] = {}

    for item in tracks_data:
        tid = int(item["track_id"])
        cls_name = str(item["class_name"])
        raw_points = sorted(item.get("timeline_points", []), key=lambda p: int(p["frame_index"]))
        if not raw_points:
            continue

        norm_points: list[NormalizedTrackPoint] = []
        by_frame: dict[int, NormalizedTrackPoint] = {}
        for pt in raw_points:
            f_idx = int(pt["frame_index"])
            ts = float(pt["timestamp_seconds"])
            nx = min(1.0, max(0.0, float(pt["center_x"]) / safe_w))
            ny = min(1.0, max(0.0, float(pt["center_y"]) / safe_h))
            conf = float(pt.get("confidence", 0.5))
            ntp = NormalizedTrackPoint(
                frame_index=f_idx,
                timestamp_seconds=ts,
                norm_x=nx,
                norm_y=ny,
                confidence=conf,
            )
            norm_points.append(ntp)
            by_frame[f_idx] = ntp

        first_pt = norm_points[0]
        last_pt = norm_points[-1]
        dx = last_pt.norm_x - first_pt.norm_x
        dy = last_pt.norm_y - first_pt.norm_y
        net_disp = math.hypot(dx, dy)

        max_disp = 0.0
        for pt in norm_points:
            d = math.hypot(pt.norm_x - first_pt.norm_x, pt.norm_y - first_pt.norm_y)
            if d > max_disp:
                max_disp = d

        is_stationary = max_disp <= cfg.stationary_displacement_norm
        direction_label = _classify_direction(dx, dy, net_disp, cfg.stationary_displacement_norm)

        profiles[tid] = TrackMotionProfile(
            track_id=tid,
            class_name=cls_name,
            first_seen_frame=int(item["first_seen_frame"]),
            last_seen_frame=int(item["last_seen_frame"]),
            first_seen_timestamp=float(item["first_seen_timestamp"]),
            last_seen_timestamp=float(item["last_seen_timestamp"]),
            duration_seconds=float(item["duration_seconds"]),
            frame_count=int(item["frame_count"]),
            avg_confidence=float(item.get("avg_confidence", 0.5)),
            max_displacement_norm=round(max_disp, 4),
            net_displacement_norm=round(net_disp, 4),
            direction_label=direction_label,
            is_stationary=is_stationary,
            started_near_edge=_is_near_edge(first_pt.norm_x, first_pt.norm_y, cfg.edge_margin_norm),
            ended_near_edge=_is_near_edge(last_pt.norm_x, last_pt.norm_y, cfg.edge_margin_norm),
            points_by_frame=by_frame,
        )

    person_profiles = [p for p in profiles.values() if p.class_name == "person"]
    object_profiles = [p for p in profiles.values() if p.class_name != "person"]

    person_object_list: list[PersonObjectInteraction] = []
    for person in person_profiles:
        for obj in object_profiles:
            shared_frames = sorted(
                set(person.points_by_frame.keys()) & set(obj.points_by_frame.keys())
            )
            if not shared_frames:
                continue

            series: list[PairwiseDistancePoint] = []
            for f_idx in shared_frames:
                p_pt = person.points_by_frame[f_idx]
                o_pt = obj.points_by_frame[f_idx]
                dist = round(math.hypot(p_pt.norm_x - o_pt.norm_x, p_pt.norm_y - o_pt.norm_y), 4)
                series.append(
                    PairwiseDistancePoint(
                        frame_index=f_idx,
                        timestamp_seconds=p_pt.timestamp_seconds,
                        distance_norm=dist,
                    )
                )

            min_pt = min(series, key=lambda d: d.distance_norm)

            # Detect approach into proximity (distance decreases by approach_delta_norm)
            approach_window: tuple[int, int, float, float, float, float] | None = None
            if len(series) >= 2:
                max_before_min = max(
                    series[: series.index(min_pt) + 1],
                    key=lambda d: d.distance_norm,
                )
                drop = max_before_min.distance_norm - min_pt.distance_norm
                if (
                    min_pt.frame_index > max_before_min.frame_index
                    and drop >= cfg.approach_delta_norm
                    and min_pt.distance_norm <= cfg.proximity_threshold_norm
                ):
                    approach_window = (
                        max_before_min.frame_index,
                        min_pt.frame_index,
                        max_before_min.timestamp_seconds,
                        min_pt.timestamp_seconds,
                        max_before_min.distance_norm,
                        min_pt.distance_norm,
                    )

            # Detect departure away from proximity (distance rises by departure_delta_norm)
            departure_window: tuple[int, int, float, float, float, float] | None = None
            if len(series) >= 2:
                min_idx = series.index(min_pt)
                after_slice = series[min_idx:]
                if len(after_slice) >= 2:
                    max_after_min = max(after_slice, key=lambda d: d.distance_norm)
                    rise = max_after_min.distance_norm - min_pt.distance_norm
                    if (
                        max_after_min.frame_index > min_pt.frame_index
                        and rise >= cfg.departure_delta_norm
                        and min_pt.distance_norm <= cfg.proximity_threshold_norm
                    ):
                        departure_window = (
                            min_pt.frame_index,
                            max_after_min.frame_index,
                            min_pt.timestamp_seconds,
                            max_after_min.timestamp_seconds,
                            min_pt.distance_norm,
                            max_after_min.distance_norm,
                        )

            # Detect distinct proximity visit windows (for repeated movement near object)
            visit_windows: list[tuple[int, int, float, float]] = []
            in_visit = False
            v_start_f = 0
            v_start_ts = 0.0
            v_end_f = 0
            v_end_ts = 0.0

            for pt in series:
                if pt.distance_norm <= cfg.proximity_threshold_norm:
                    if not in_visit:
                        in_visit = True
                        v_start_f = pt.frame_index
                        v_start_ts = pt.timestamp_seconds
                    v_end_f = pt.frame_index
                    v_end_ts = pt.timestamp_seconds
                else:
                    if in_visit:
                        visit_windows.append((v_start_f, v_end_f, v_start_ts, v_end_ts))
                        in_visit = False
            if in_visit:
                visit_windows.append((v_start_f, v_end_f, v_start_ts, v_end_ts))

            person_object_list.append(
                PersonObjectInteraction(
                    person_track_id=person.track_id,
                    object_track_id=obj.track_id,
                    object_class_name=obj.class_name,
                    distance_series=series,
                    min_distance_norm=min_pt.distance_norm,
                    min_distance_frame=min_pt.frame_index,
                    min_distance_timestamp=min_pt.timestamp_seconds,
                    approach_window=approach_window,
                    departure_window=departure_window,
                    proximity_visit_windows=visit_windows,
                )
            )

    person_person_list: list[PersonPersonInteraction] = []
    for idx_a in range(len(person_profiles)):
        for idx_b in range(idx_a + 1, len(person_profiles)):
            pa = person_profiles[idx_a]
            pb = person_profiles[idx_b]
            shared = sorted(set(pa.points_by_frame.keys()) & set(pb.points_by_frame.keys()))
            close_frames: list[int] = []
            close_timestamps: list[float] = []
            min_dist = 1.0

            for f_idx in shared:
                pt_a = pa.points_by_frame[f_idx]
                pt_b = pb.points_by_frame[f_idx]
                dist = math.hypot(pt_a.norm_x - pt_b.norm_x, pt_a.norm_y - pt_b.norm_y)
                if dist <= cfg.multi_person_proximity_norm:
                    close_frames.append(f_idx)
                    close_timestamps.append(pt_a.timestamp_seconds)
                    if dist < min_dist:
                        min_dist = dist

            if len(close_frames) >= cfg.multi_person_min_frames:
                person_person_list.append(
                    PersonPersonInteraction(
                        track_id_a=pa.track_id,
                        track_id_b=pb.track_id,
                        shared_proximity_frames=close_frames,
                        start_timestamp=close_timestamps[0],
                        end_timestamp=close_timestamps[-1],
                        min_distance_norm=round(min_dist, 4),
                    )
                )

    return InteractionAnalysisResult(
        frame_width=safe_w,
        frame_height=safe_h,
        min_frame_index=min_frame_idx,
        max_frame_index=max_frame_idx,
        track_profiles=profiles,
        person_object_interactions=person_object_list,
        person_person_interactions=person_person_list,
    )
