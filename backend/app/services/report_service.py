from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models.analysis import Analysis
from app.models.detection import Detection
from app.models.event import Event
from app.models.evidence import Evidence
from app.models.live_session import LiveEvent, LiveSession
from app.models.track import Track
from app.models.video import Video


def _fmt_hms(seconds: float | None) -> str:
    if seconds is None:
        return "Unavailable"
    total = max(0, int(round(seconds)))
    hrs = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d} ({seconds:.2f}s)"


def _resolve_safe_evidence_file(file_path: str, evidence_root: Path) -> Path | None:
    project_root = BACKEND_DIR.parent
    candidate = (project_root / file_path).resolve()
    try:
        candidate.relative_to(evidence_root.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def generate_analysis_pdf_report(*, analysis: Analysis, db: Session) -> Path:
    """Build a structured ReportLab PDF intelligence report from actual DB/analysis records."""
    settings = get_settings()
    reports_dir = (settings.resolved_reports_dir / analysis.id).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = reports_dir / f"nemesis_x_report_{analysis.id[:8]}.pdf"

    video = db.query(Video).filter(Video.id == analysis.video_id).first()
    tracks = (
        db.query(Track)
        .filter(Track.analysis_id == analysis.id)
        .order_by(Track.first_seen_timestamp.asc(), Track.track_id.asc())
        .all()
    )
    detections = db.query(Detection).filter(Detection.analysis_id == analysis.id).all()
    events = (
        db.query(Event)
        .filter(Event.analysis_id == analysis.id)
        .order_by(Event.start_timestamp.asc(), Event.end_timestamp.asc())
        .all()
    )
    evidence_items = (
        db.query(Evidence)
        .filter(Evidence.analysis_id == analysis.id, Evidence.user_id == analysis.user_id)
        .order_by(Evidence.timestamp_seconds.asc(), Evidence.frame_number.asc())
        .all()
    )

    processed_dir = settings.resolved_processed_dir / analysis.id
    meta: dict[str, Any] = {}
    if (processed_dir / "metadata.json").exists():
        try:
            meta = json.loads((processed_dir / "metadata.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}

    class_counts = Counter(det.class_name for det in detections)
    total_detections = len(detections)
    total_tracks = len(tracks)
    total_events = len(events)

    styles = getSampleStyleSheet()
    brand_title = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )
    tagline_style = ParagraphStyle(
        "Tagline",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#111827"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyTextClean",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )
    muted_style = ParagraphStyle(
        "MutedNote",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=4,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"NEMESIS-X Video Intelligence Report ({analysis.id})",
        author="NEMESIS-X",
    )

    story: list[Any] = []
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Branding & Report Header
    story.append(Paragraph("NEMESIS-X — Video Intelligence Report", brand_title))
    story.append(Paragraph("Beyond Detection. Into Understanding.", tagline_style))

    # 2–8. Core Metadata & Processing Summary Table
    orig_filename = video.original_filename if video else "Unknown"
    duration_str = _fmt_hms(video.duration_seconds if video else meta.get("duration_seconds"))
    dims = (
        f"{video.width}x{video.height}"
        if video and video.width and video.height
        else "Unavailable"
    )
    fps_val = meta.get("fps", "Unavailable")

    overview_rows = [
        ["Analysis ID", analysis.id],
        ["Original Video Filename", orig_filename],
        ["Video Duration", duration_str],
        ["Resolution & FPS", f"{dims} | FPS: {fps_val}"],
        [
            "Processing Summary",
            f"Status: {analysis.status} | Frames Scanned: {analysis.processed_frames}/{analysis.total_frames} "
            f"| Extracted Frames: {analysis.extracted_frames} | Sampling: Every {analysis.sampling_interval} frame(s)",
        ],
        ["Total Detected Objects", str(total_detections)],
        ["Total Unique Tracking IDs", str(total_tracks)],
        ["Total Discovered Events", str(total_events)],
        ["Report Generated", generated_at],
    ]
    overview_table = Table(overview_rows, colWidths=[1.85 * inch, 5.15 * inch])
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F8FC")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(overview_table)
    story.append(Spacer(1, 10))

    # Detected categories breakdown
    story.append(Paragraph("Object Detection Breakdown", h2_style))
    if class_counts:
        breakdown_text = ", ".join(f"{cls}: {cnt}" for cls, cnt in class_counts.most_common())
        story.append(
            Paragraph(
                f"Detected {total_detections} object instance(s) using CPU-only {settings.yolo_model_name}: {breakdown_text}.",
                body_style,
            )
        )
    else:
        story.append(
            Paragraph(
                "No objects were detected above the configured confidence threshold.",
                body_style,
            )
        )

    # 12. Tracking Information
    story.append(Paragraph("Tracking Information (Temporal Memory)", h2_style))
    if tracks:
        track_rows = [
            ["Track ID", "Class", "First Seen", "Last Seen", "Duration", "Frames", "Avg Conf."]
        ]
        for trk in tracks[:25]:
            track_rows.append(
                [
                    f"T{trk.track_id:03d}",
                    trk.class_name,
                    _fmt_hms(trk.first_seen_timestamp),
                    _fmt_hms(trk.last_seen_timestamp),
                    f"{trk.duration_seconds:.1f}s",
                    str(trk.frame_count),
                    f"{int(round(trk.avg_confidence * 100))}%",
                ]
            )
        track_table = Table(
            track_rows,
            colWidths=[0.7 * inch, 0.9 * inch, 1.35 * inch, 1.35 * inch, 0.75 * inch, 0.65 * inch, 0.8 * inch],
        )
        track_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(track_table)
    else:
        story.append(Paragraph("No persistent object tracks were recorded.", body_style))

    # 9, 10, 11, 13, 14. Discovered Events & Evidence Images
    story.append(Paragraph("Discovered Events & Evidence", h2_style))
    evidence_root = settings.resolved_evidence_dir
    evidence_by_event: dict[str, list[Evidence]] = {}
    for ev_item in evidence_items:
        evidence_by_event.setdefault(ev_item.event_id, []).append(ev_item)

    if not events:
        story.append(
            Paragraph(
                "No supported event patterns were identified in this analysis.",
                body_style,
            )
        )
    else:
        review_events = [
            ev for ev in events if (ev.explanation_payload or {}).get("requires_human_review")
        ]
        story.append(
            Paragraph(
                f"Important Observations: {len(events)} event(s) identified; "
                f"{len(review_events)} event(s) flagged for human review.",
                body_style,
            )
        )

        for idx, evt in enumerate(events, start=1):
            expl = evt.explanation_payload or {}
            track_str = ", ".join(f"T{t:03d}" for t in (evt.involved_track_ids or [])) or "None"
            story.append(
                Paragraph(
                    f"<b>{idx}. {evt.title}</b> [{evt.severity.upper()} | Confidence: {int(round(evt.confidence * 100))}%]",
                    body_style,
                )
            )
            story.append(
                Paragraph(
                    f"Timestamps: {_fmt_hms(evt.start_timestamp)} → {_fmt_hms(evt.end_timestamp)} | "
                    f"Involved Tracks: {track_str}",
                    muted_style,
                )
            )
            story.append(Paragraph(evt.description, body_style))

            seq = expl.get("observed_sequence", [])
            if seq:
                seq_html = "<br/>".join(f"• {line}" for line in seq)
                story.append(Paragraph(f"<b>Observed Sequence:</b><br/>{seq_html}", muted_style))

            # Embed up to 2 relevant annotated/original evidence images per event
            ev_artifacts = evidence_by_event.get(evt.id, [])
            preferred = sorted(
                ev_artifacts,
                key=lambda item: (
                    0
                    if item.evidence_type == "annotated_tracking"
                    else 1
                    if item.evidence_type == "annotated_detection"
                    else 2,
                    item.timestamp_seconds,
                ),
            )[:2]

            img_cells: list[Any] = []
            for art in preferred:
                resolved = _resolve_safe_evidence_file(art.file_path, evidence_root)
                if resolved is not None:
                    try:
                        img = Image(str(resolved), width=3.1 * inch, height=1.75 * inch, kind="proportional")
                        caption = Paragraph(
                            f"{art.evidence_type.replace('_', ' ').title()} · Frame #{art.frame_number} ({art.timestamp_seconds:.2f}s)",
                            muted_style,
                        )
                        img_cells.append([img, caption])
                    except Exception:
                        continue

            if img_cells:
                row = [
                    Table([[c[0]], [c[1]]], colWidths=[3.3 * inch])
                    for c in img_cells
                ]
                img_table = Table([row], colWidths=[3.45 * inch] * len(row))
                img_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(img_table)

            story.append(Spacer(1, 8))

    # 15. Limitations & Human-Review Disclaimer
    story.append(Paragraph("Limitations & Human-Review Disclaimer", h2_style))
    story.append(
        Paragraph(
            "This report was generated automatically from sampled video frames (CPU-only YOLO11n "
            "detection, ByteTrack association, and rule-based 2D normalized image-plane heuristics). "
            "Without camera calibration, pixel distances do not represent physical meters. "
            "Visual proximity or stationary duration cannot establish ownership, theft, or intent. "
            "All flagged events and evidence frames must be reviewed by a qualified human operator.",
            muted_style,
        )
    )

    doc.build(story)
    return pdf_path


def generate_live_session_pdf_report(*, live_session: LiveSession, db: Session) -> Path:
    """Build a ReportLab PDF intelligence report for an owned live webcam monitoring session."""
    settings = get_settings()
    reports_dir = (settings.resolved_reports_dir / f"live_{live_session.id}").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = reports_dir / f"nemesis_x_live_report_{live_session.id[:8]}.pdf"

    live_events = (
        db.query(LiveEvent)
        .filter(LiveEvent.session_id == live_session.id, LiveEvent.user_id == live_session.user_id)
        .order_by(LiveEvent.timestamp_seconds.asc(), LiveEvent.frame_index.asc())
        .all()
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LiveReportTitle",
        parent=styles["Heading1"],
        fontSize=19,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )
    h2_style = ParagraphStyle(
        "LiveSectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "LiveBodyText",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#111827"),
    )
    muted_style = ParagraphStyle(
        "LiveMutedText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    story: list[Any] = [
        Paragraph("NEMESIS-X Live Monitoring Report", title_style),
        Paragraph("Live Webcam Intelligence · Evidence &amp; Event Summary", muted_style),
        Spacer(1, 10),
        Paragraph("Live Session Metadata", h2_style),
    ]

    summary_rows = [
        ["Session ID", live_session.id],
        ["Status", live_session.status],
        ["Started At (UTC)", live_session.started_at.strftime("%Y-%m-%d %H:%M:%S")],
        [
            "Resolution",
            f"{live_session.frame_width}x{live_session.frame_height}"
            if live_session.frame_width and live_session.frame_height
            else "Unavailable",
        ],
        ["Frames Processed", str(live_session.frames_processed)],
        ["Objects Detected (Total)", str(live_session.total_detections)],
        ["Unique Tracks", str(live_session.unique_tracks_count)],
        ["Events Discovered", str(len(live_events))],
    ]
    tbl = Table(summary_rows, colWidths=[2.1 * inch, 4.7 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F8FC")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([tbl, Spacer(1, 10), Paragraph("Discovered Live Events &amp; Evidence", h2_style)])

    live_root = settings.resolved_live_dir
    if not live_events:
        story.append(Paragraph("No supported events were discovered during this live session.", body_style))
    else:
        for idx, evt in enumerate(live_events, start=1):
            expl = evt.explanation_payload or {}
            track_str = ", ".join(f"T{t:03d}" for t in (evt.involved_track_ids or [])) or "None"
            story.append(
                Paragraph(
                    f"<b>{idx}. {evt.title}</b> [{evt.severity.upper()} | Confidence: {int(round(evt.confidence * 100))}%]",
                    body_style,
                )
            )
            story.append(
                Paragraph(
                    f"Timestamp: {_fmt_hms(evt.timestamp_seconds)} | Frame #{evt.frame_index + 1} | Tracks: {track_str}",
                    muted_style,
                )
            )
            story.append(Paragraph(evt.description, body_style))
            if evt.snapshot_path:
                resolved = _resolve_safe_evidence_file(evt.snapshot_path, live_root)
                if resolved is not None:
                    try:
                        img = Image(str(resolved), width=3.2 * inch, height=1.8 * inch, kind="proportional")
                        story.append(img)
                    except Exception:
                        pass
            if expl.get("why_flagged"):
                story.append(Paragraph(f"Reason: {expl['why_flagged']}", muted_style))
            story.append(Spacer(1, 8))

    story.append(Paragraph("Limitations &amp; Human-Review Disclaimer", h2_style))
    story.append(
        Paragraph(
            "Generated automatically from real webcam session detections (CPU-only YOLO11n and "
            "isolated ByteTrack). Visual heuristics describe possible movement or interactions only "
            "and must be verified by a human operator.",
            muted_style,
        )
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    doc.build(story)
    return pdf_path
