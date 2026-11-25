from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class RestrictedZone:
    """Normalized [0..1] rectangular zone for area-based monitoring."""

    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def contains(self, nx: float, ny: float) -> bool:
        return self.x1 <= nx <= self.x2 and self.y1 <= ny <= self.y2


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

    # Pickup & placement thresholds
    object_move_disp_norm: float = 0.045
    co_movement_max_dist_norm: float = 0.28
    co_movement_corr_threshold: float = 0.45
    co_movement_min_frames: int = 2
    placement_min_stationary_frames: int = 2

    # Occlusion & ID switch tolerance
    occlusion_gap_max_frames: int = 6
    occlusion_dist_norm: float = 0.14

    # Anomaly thresholds
    sudden_accel_threshold: float = 0.25
    running_speed_threshold: float = 0.22
    direction_reversal_cos_threshold: float = -0.5
    min_reversals_for_anomaly: int = 2
    prolonged_person_stationary_seconds: float = 8.0
    burst_window_seconds: float = 15.0
    burst_min_events: int = 4
    restricted_zones: tuple[RestrictedZone, ...] = ()
    operating_hours_utc: tuple[int, int] | None = None


@dataclass(frozen=True)
class NormalizedTrackPoint:
    """Normalized [0..1] spatial and kinematic snapshot for a tracked object."""

    frame_index: int
    timestamp_seconds: float
    norm_x: float
    norm_y: float
    confidence: float
    vx: float = 0.0
    vy: float = 0.0
    speed: float = 0.0
    accel: float = 0.0
    bbox_norm: tuple[float, float, float, float] | None = None


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
    initial_norm_pos: tuple[float, float]
    last_norm_pos: tuple[float, float]
    max_speed: float = 0.0
    max_accel: float = 0.0
    direction_reversals: int = 0
    points_by_frame: dict[int, NormalizedTrackPoint] = field(default_factory=dict)


@dataclass(frozen=True)
class PairwiseDistancePoint:
    """Normalized center-to-center distance between two tracks at one frame."""

    frame_index: int
    timestamp_seconds: float
    distance_norm: float


@dataclass(frozen=True)
class PersonObjectInteraction:
    """Computed proximity, approach, departure, pickup, placement, and visit cycles."""

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
    # Advanced interaction fields
    co_movement_frames: list[int] = field(default_factory=list)
    co_movement_score: float = 0.0
    object_moved_after_interaction: bool = False
    object_displacement_norm: float = 0.0
    is_possible_pickup: bool = False
    is_possible_placement: bool = False
    pickup_window: tuple[int, int, float, float] | None = None
    placement_window: tuple[int, int, float, float] | None = None


@dataclass(frozen=True)
class MultiPersonObjectAssociation:
    """Associates an object with multiple nearby people and ranks the strongest candidate."""

    object_track_id: int
    object_class_name: str
    candidate_person_ids: list[int]
    primary_person_id: int | None
    association_uncertainty: str  # "low", "medium", "high"
    reason: str
    start_timestamp: float
    end_timestamp: float
    frame_ids: list[int]


@dataclass(frozen=True)
class OcclusionIdSwitchCandidate:
    """Detects possible track ID switch due to brief occlusion."""

    class_name: str
    prev_track_id: int
    next_track_id: int
    gap_frames: int
    spatial_distance_norm: float
    prev_end_timestamp: float
    next_start_timestamp: float


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
    multi_person_object_associations: list[MultiPersonObjectAssociation] = field(default_factory=list)
    possible_id_switches: list[OcclusionIdSwitchCandidate] = field(default_factory=list)


@dataclass
class SessionTemporalMemory:
    """Isolated per-session temporal memory for tracking histories and event sequences."""

    session_id: str
    person_track_ids: set[int] = field(default_factory=set)
    object_track_ids: set[int] = field(default_factory=set)
    object_initial_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    object_last_positions: dict[int, tuple[float, float]] = field(default_factory=dict)
    relationship_history: dict[tuple[int, int], list[dict[str, Any]]] = field(default_factory=dict)
    area_history: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    previous_event_sequences: list[dict[str, Any]] = field(default_factory=list)


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


def _cosine_similarity(vx1: float, vy1: float, vx2: float, vy2: float) -> float:
    mag1 = math.hypot(vx1, vy1)
    mag2 = math.hypot(vx2, vy2)
    if mag1 < 1e-5 or mag2 < 1e-5:
        return 0.0
    return (vx1 * vx2 + vy1 * vy2) / (mag1 * mag2)


def analyze_track_interactions(
    *,
    tracks_data: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
    all_frame_indices: list[int],
    config: InteractionConfig | None = None,
    memory: SessionTemporalMemory | None = None,
) -> InteractionAnalysisResult:
    """Compute normalized motion profiles, kinematics, and pairwise interactions."""
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

        prev_nx: float | None = None
        prev_ny: float | None = None
        prev_ts: float | None = None
        prev_vx: float = 0.0
        prev_vy: float = 0.0
        prev_speed: float = 0.0
        max_speed = 0.0
        max_accel = 0.0
        reversals = 0

        for pt in raw_points:
            f_idx = int(pt["frame_index"])
            ts = float(pt["timestamp_seconds"])
            nx = min(1.0, max(0.0, float(pt["center_x"]) / safe_w))
            ny = min(1.0, max(0.0, float(pt["center_y"]) / safe_h))
            conf = float(pt.get("confidence", 0.5))

            bbox_norm: tuple[float, float, float, float] | None = None
            if "bbox" in pt and isinstance(pt["bbox"], dict):
                b = pt["bbox"]
                bbox_norm = (
                    min(1.0, max(0.0, float(b.get("x1", 0.0)) / safe_w)),
                    min(1.0, max(0.0, float(b.get("y1", 0.0)) / safe_h)),
                    min(1.0, max(0.0, float(b.get("x2", 0.0)) / safe_w)),
                    min(1.0, max(0.0, float(b.get("y2", 0.0)) / safe_h)),
                )

            vx = 0.0
            vy = 0.0
            speed = 0.0
            accel = 0.0
            if prev_nx is not None and prev_ny is not None and prev_ts is not None:
                dt = max(1e-3, ts - prev_ts)
                vx = (nx - prev_nx) / dt
                vy = (ny - prev_ny) / dt
                speed = math.hypot(vx, vy)
                accel = abs(speed - prev_speed) / dt
                if speed > max_speed:
                    max_speed = speed
                if accel > max_accel:
                    max_accel = accel

                # Check sharp direction reversal when moving meaningfully
                if prev_speed > 0.03 and speed > 0.03:
                    cos_val = _cosine_similarity(prev_vx, prev_vy, vx, vy)
                    if cos_val <= cfg.direction_reversal_cos_threshold:
                        reversals += 1

            ntp = NormalizedTrackPoint(
                frame_index=f_idx,
                timestamp_seconds=ts,
                norm_x=nx,
                norm_y=ny,
                confidence=conf,
                vx=vx,
                vy=vy,
                speed=speed,
                accel=accel,
                bbox_norm=bbox_norm,
            )
            norm_points.append(ntp)
            by_frame[f_idx] = ntp

            prev_nx, prev_ny, prev_ts = nx, ny, ts
            prev_vx, prev_vy, prev_speed = vx, vy, speed

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
            initial_norm_pos=(first_pt.norm_x, first_pt.norm_y),
            last_norm_pos=(last_pt.norm_x, last_pt.norm_y),
            max_speed=round(max_speed, 4),
            max_accel=round(max_accel, 4),
            direction_reversals=reversals,
            points_by_frame=by_frame,
        )

        # Update isolated session temporal memory if provided
        if memory is not None:
            if cls_name == "person":
                memory.person_track_ids.add(tid)
            else:
                memory.object_track_ids.add(tid)
                if tid not in memory.object_initial_positions:
                    memory.object_initial_positions[tid] = (first_pt.norm_x, first_pt.norm_y)
                memory.object_last_positions[tid] = (last_pt.norm_x, last_pt.norm_y)

    person_profiles = [p for p in profiles.values() if p.class_name == "person"]
    object_profiles = [p for p in profiles.values() if p.class_name != "person"]

    # Detect possible occlusion / ID switches within same class
    possible_id_switches: list[OcclusionIdSwitchCandidate] = []
    profiles_by_class: dict[str, list[TrackMotionProfile]] = {}
    for prof in profiles.values():
        profiles_by_class.setdefault(prof.class_name, []).append(prof)

    for cls_name, cls_list in profiles_by_class.items():
        if len(cls_list) < 2:
            continue
        sorted_cls = sorted(cls_list, key=lambda p: p.first_seen_frame)
        for i in range(len(sorted_cls)):
            for j in range(i + 1, len(sorted_cls)):
                p_prev = sorted_cls[i]
                p_next = sorted_cls[j]
                gap = p_next.first_seen_frame - p_prev.last_seen_frame
                if 1 <= gap <= cfg.occlusion_gap_max_frames:
                    dist = math.hypot(
                        p_next.initial_norm_pos[0] - p_prev.last_norm_pos[0],
                        p_next.initial_norm_pos[1] - p_prev.last_norm_pos[1],
                    )
                    if dist <= cfg.occlusion_dist_norm:
                        possible_id_switches.append(
                            OcclusionIdSwitchCandidate(
                                class_name=cls_name,
                                prev_track_id=p_prev.track_id,
                                next_track_id=p_next.track_id,
                                gap_frames=gap,
                                spatial_distance_norm=round(dist, 4),
                                prev_end_timestamp=p_prev.last_seen_timestamp,
                                next_start_timestamp=p_next.first_seen_timestamp,
                            )
                        )

    person_object_list: list[PersonObjectInteraction] = []
    object_candidates_map: dict[int, list[PersonObjectInteraction]] = {}

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

            # Detect approach into proximity
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

            # Detect departure away from proximity
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

            # Detect distinct proximity visit windows
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

            # Analyze co-movement & object displacement for Pickup / Placement
            co_move_frames: list[int] = []
            co_sims: list[float] = []
            for pt in series:
                if pt.distance_norm <= cfg.co_movement_max_dist_norm:
                    p_pt = person.points_by_frame[pt.frame_index]
                    o_pt = obj.points_by_frame[pt.frame_index]
                    if p_pt.speed > 0.015 and o_pt.speed > 0.015:
                        cos_sim = _cosine_similarity(p_pt.vx, p_pt.vy, o_pt.vx, o_pt.vy)
                        if cos_sim >= cfg.co_movement_corr_threshold:
                            co_move_frames.append(pt.frame_index)
                            co_sims.append(cos_sim)

            co_move_score = round(sum(co_sims) / len(co_sims), 3) if co_sims else 0.0
            obj_moved = obj.max_displacement_norm >= cfg.object_move_disp_norm

            is_possible_pickup = False
            pickup_window: tuple[int, int, float, float] | None = None
            if min_pt.distance_norm <= cfg.proximity_threshold_norm and obj_moved:
                if len(co_move_frames) >= cfg.co_movement_min_frames:
                    is_possible_pickup = True
                    f_s = approach_window[0] if approach_window else min(co_move_frames[0], min_pt.frame_index)
                    f_e = co_move_frames[-1]
                    ts_s = person.points_by_frame[f_s].timestamp_seconds if f_s in person.points_by_frame else min_pt.timestamp_seconds
                    ts_e = person.points_by_frame[f_e].timestamp_seconds if f_e in person.points_by_frame else obj.last_seen_timestamp
                    pickup_window = (f_s, f_e, ts_s, ts_e)

            is_possible_placement = False
            placement_window: tuple[int, int, float, float] | None = None
            if min_pt.distance_norm <= cfg.proximity_threshold_norm and (
                departure_window is not None or person.last_seen_frame < obj.last_seen_frame
            ):
                depart_f = departure_window[1] if departure_window else person.last_seen_frame
                after_obj_pts = [
                    pt for f, pt in sorted(obj.points_by_frame.items()) if f >= depart_f
                ]
                if len(after_obj_pts) >= cfg.placement_min_stationary_frames:
                    base_pt = after_obj_pts[0]
                    post_disp = max(
                        math.hypot(pt.norm_x - base_pt.norm_x, pt.norm_y - base_pt.norm_y)
                        for pt in after_obj_pts
                    )
                    if post_disp <= cfg.stationary_displacement_norm:
                        is_possible_placement = True
                        placement_window = (
                            min_pt.frame_index,
                            obj.last_seen_frame,
                            min_pt.timestamp_seconds,
                            obj.last_seen_timestamp,
                        )

            inter = PersonObjectInteraction(
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
                co_movement_frames=co_move_frames,
                co_movement_score=co_move_score,
                object_moved_after_interaction=obj_moved,
                object_displacement_norm=obj.max_displacement_norm,
                is_possible_pickup=is_possible_pickup,
                is_possible_placement=is_possible_placement,
                pickup_window=pickup_window,
                placement_window=placement_window,
            )
            person_object_list.append(inter)

            if min_pt.distance_norm <= cfg.proximity_threshold_norm:
                object_candidates_map.setdefault(obj.track_id, []).append(inter)

            if memory is not None:
                memory.relationship_history.setdefault((person.track_id, obj.track_id), []).append(
                    {
                        "min_distance_norm": min_pt.distance_norm,
                        "is_possible_pickup": is_possible_pickup,
                        "is_possible_placement": is_possible_placement,
                        "timestamp": min_pt.timestamp_seconds,
                    }
                )

    # Multi-person association resolution per object
    multi_associations: list[MultiPersonObjectAssociation] = []
    for obj_tid, inters in object_candidates_map.items():
        if len(inters) >= 2:
            scored: list[tuple[float, PersonObjectInteraction]] = []
            for inter in inters:
                dist_score = max(0.0, 1.0 - (inter.min_distance_norm / max(cfg.proximity_threshold_norm, 0.01)))
                co_score = len(inter.co_movement_frames) * 0.4 + inter.co_movement_score * 0.6
                total_s = dist_score + co_score + (1.0 if inter.is_possible_pickup else 0.0)
                scored.append((total_s, inter))

            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_inter = scored[0]
            second_score, _ = scored[1]

            margin = best_score - second_score
            if margin >= 0.6 and best_inter.is_possible_pickup:
                uncertainty = "low"
            elif margin >= 0.2:
                uncertainty = "medium"
            else:
                uncertainty = "high"

            cand_ids = [i.person_track_id for _, i in scored]
            all_frames = sorted(
                {pt.frame_index for i in inters for pt in i.distance_series if pt.distance_norm <= cfg.proximity_threshold_norm}
            )
            ts_start = min(i.min_distance_timestamp for i in inters)
            ts_end = max(i.distance_series[-1].timestamp_seconds for i in inters)

            multi_associations.append(
                MultiPersonObjectAssociation(
                    object_track_id=obj_tid,
                    object_class_name=best_inter.object_class_name,
                    candidate_person_ids=cand_ids,
                    primary_person_id=best_inter.person_track_id if uncertainty != "high" else None,
                    association_uncertainty=uncertainty,
                    reason=(
                        f"Multiple people ({', '.join(f'P{p:03d}' for p in cand_ids)}) approached "
                        f"{best_inter.object_class_name} O{obj_tid:03d}. "
                        + (
                            f"Strongest motion & proximity support for P{best_inter.person_track_id:03d} (uncertainty: {uncertainty})."
                            if uncertainty != "high"
                            else "Association remains uncertain due to overlapping proximity."
                        )
                    ),
                    start_timestamp=ts_start,
                    end_timestamp=ts_end,
                    frame_ids=all_frames or [best_inter.min_distance_frame],
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
        multi_person_object_associations=multi_associations,
        possible_id_switches=possible_id_switches,
    )
