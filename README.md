# NEMESIS-X

**Contextual AI Video Intelligence for Real-Time Anomaly Detection, Bilingual Alerts & Automated Evidence Reporting**

---

## Objective

NEMESIS-X is an AI-powered video intelligence system designed to detect unusual events through multi-stage **object detection**, **multi-object tracking**, **temporal analysis**, and **contextual reasoning**. Rather than relying solely on isolated frame classifications, NEMESIS-X understands how scenes evolve over time to surface meaningful anomalies and produce:

- **Timestamped Visual Evidence** — Annotated keyframes and video clips capturing detected events.
- **Real-Time Bilingual Alerts** — Actionable notifications delivered in both **Kannada** and **English**.
- **Intelligent Video Reports** — Structured incident summaries with context, severity, timelines, and supporting evidence.

---

## Behaviour Intelligence

The authenticated Behaviour Intelligence workspace combines tracked image-plane movement summaries with the existing temporal interaction and event pipeline for recorded analyses and live webcam sessions. It exposes movement direction changes, walking-/running-like estimates, repeated interactions, explainable anomaly scores, event correlations, and supporting evidence.

Scores reweight the existing explainable components using configurable per-session weights (which must sum to 1); events without a stored score breakdown are not assigned one. Movement speeds are normalized image coordinates per second, not physical speeds. Session baselines are configurable descriptive rules, remain scoped to their video or live session, and explicitly report when history is insufficient; no statistical learning model is claimed.

The API is available under `/api/v1/behavior`: use `/analysis/{analysis_id}` or `/live/{session_id}` for reports, their `/sequences`, `/anomalies`, and `/summary` subroutes for filtered records and summaries, and the corresponding `/baseline` `PUT` route to save per-session rules. All endpoints enforce authenticated user ownership.

## Smart Zone Intelligence

Smart Zones stores polygon vertices as normalized `[x, y]` values under exactly one owned video or live session. The frame editor supports restricted, safe, monitoring, entry, and exit areas, color, confirmation frames, event cooldown, loiter duration, restricted-group size, and alert preferences. CPU-friendly polygon checks reuse existing YOLO and ByteTrack outputs; transitions require the configured consecutive tracked observations, and an untracked detection cannot generate a zone event.

Completed video zone events are generated alongside existing events by `POST /api/v1/analysis/{analysis_id}/discover-events`; live zones are evaluated as tracked frames arrive. Existing event/evidence persistence stores recorded annotated frames and live annotated snapshots. A loitering event reports observed zone duration only and does not infer intent. Live track/zone state is isolated per session and cleared when monitoring stops.

The authenticated zone API includes `POST /api/v1/zones`, `GET /api/v1/zones` (optional `video_id` or `live_session_id`), `PATCH /api/v1/zones/{zone_id}`, `DELETE /api/v1/zones/{zone_id}`, and source-specific `/analysis/{analysis_id}/events|activity`, `/live/{session_id}/events|activity`, and `/video/{video_id}/activity` routes under `/api/v1/zones`. The latest live preview is available only to its session owner at `/api/v1/live/{session_id}/latest-frame`.

## Investigation Workspace

The authenticated Investigation Workspace links existing completed video analyses and stopped live monitoring sessions without copying or changing their source media. Active live sessions cannot be linked as completed investigations. Investigations have private notes and an Open, Reviewing, or Closed status. Tracks, events, and notes are scoped to a linked source; a repeated track ID in another source is a different track and is never treated as a shared identity. Track labels include the entity category and source context.

The API is under `/api/v1/investigations`. It supports investigation create/list/detail/update/delete, linking and unlinking sources, searching tracks and loading source-scoped track details, linking and unlinking events and tracks, filtered/paginated timelines, relationship graphs, evidence references, and private note create/update/delete. Timeline filters include source, event category, source-scoped track ID, severity, and date. Date filters use the analysis creation date or live-session start date; video timestamps remain source-relative and different sources are not synchronized. The graph only represents stored event associations and explicitly recorded person/object track references; uncertain links retain their uncertainty and unsupported relationships are not inferred.

Investigation records and links are stored in the `investigations`, `investigation_sources`, `investigation_events`, `investigation_tracks`, and `investigation_notes` tables. This project initializes new tables through its existing SQLAlchemy `create_all` startup path and does not currently use Alembic migrations. All investigation and linked-source operations enforce authenticated ownership. Deleting an investigation removes only its private notes and links; it does not delete the original analyses, events, videos, or evidence.

Live investigation data is limited to persisted live events, snapshots, and recent track samples available from the source session. A continuous live recording is not claimed or reconstructed. Evidence is served through existing authenticated evidence endpoints; original evidence files and uploaded videos remain unchanged. User-written investigation notes are distinct from system-generated event explanations; note edit history is not available.

## Intelligent Video Search and Object Labels

The authenticated Intelligent Video Search workspace searches stored recorded detections, tracks, events, persisted live events, recent live track samples, and evidence references. Deterministic parsing supports source-local `T001` track codes (and `P001`/`O001` person/object role filters), common object classes, interaction/pickup/unattended/zone/anomaly terms, and source-relative `MM:SS` or `HH:MM:SS` ranges. Unrecognized searches return supported filter guidance. Search is database-backed, does not send media to an external service, and limits each request to a bounded set of stored candidates. Live results only reflect persisted session data; continuous live video is not archived.

The API is available at `/api/v1/search/intelligence` and `/api/v1/search/tracks`; both require authentication and apply owner/source filters. Search results include matching track labels, timestamps, confidence/severity where stored, and existing evidence URLs. Recorded results can open the original video and seek to the stored event timestamp; live sessions without archived video expose their saved evidence instead.

Recorded extracted frames, synchronized track playback, and live processed-frame previews share configurable object overlays. Labels use actual backend classes, confidence values, and ByteTrack IDs, with category colors, collision-aware placement, compact/detailed modes, and controls for original/annotated view, labels, IDs, confidence, and boxes. Live labels are drawn over the exact captured frame associated with the returned detection set. Overlays are rendered in the browser and do not modify uploaded videos or evidence files.

## Persistent Identity Recognition

The Unique Entity Intelligence workspace (`/dashboard/identities`) groups tracker fragments only within the selected recorded analysis or live session. It preserves original `T###` track IDs while assigning independent anonymous `P###` and `O###` labels. It supports filtering by identity, tracker ID, category, and appearance count; viewing stored track evidence and related events; and owner-authorized manual reassignment or separation.

Automatic comparisons use lightweight CPU-only HSV color, brightness, edge-orientation, and shape descriptors. Person crops exclude their upper 18% and no face recognition, external service, or trained re-identification model is used. Person/object match cutoffs are heuristic similarity scores (0.87/0.92) with ambiguity margins (0.05/0.08); they are not calibrated probabilities. Automatically linked identities remain marked probable, while weak, blurry, ambiguous, or non-distinctive object appearances remain separate or unknown. A visual match is not proof of identity.

The authenticated API is under `/api/v1/identities`: list/search one source with `GET /`, aggregate counts with `GET /counts`, inspect a record with `GET /{identity_id}`, correct a tracker association with `PATCH /{identity_id}/tracks/{track_id}`, and retrieve its stored appearance evidence with `GET /{identity_id}/tracks/{track_id}/evidence`. Source and user ownership are checked for every operation. Identity records use the existing SQLAlchemy startup table-creation path; original recordings and track IDs are not modified. No cross-video or cross-session identity recognition is claimed.

## Browser-Compatible Investigation Playback

Saved-video playback checks the source container, codecs, pixel format, and MP4 fast-start metadata before loading it. Compatible H.264/yuv420p MP4 files with AAC audio (or no audio) play directly; other supported inputs get a separate H.264/yuv420p MP4 copy with optional AAC audio and fast-start metadata under the configured playback directory. The upload is never overwritten. The authenticated API uses `POST /api/v1/videos/{video_id}/playback/prepare`, `GET /api/v1/videos/{video_id}/playback/status`, and `GET /api/v1/videos/{video_id}/playback`. Conversion failure or missing FFmpeg is shown explicitly and leaves evidence-frame navigation available. FFmpeg is provided by the `imageio-ffmpeg` backend dependency. Video object URLs are created after playback data loads and revoked only when the owning component is cleaned up, avoiding premature revocation under React Strict Mode.

Run the backend from `backend/` with `python -m uvicorn app.main:app --reload`; run the frontend from `frontend/` with `npm run dev`. Validate the backend with `python -m pytest tests -q` and build the frontend with `npm run build`.

---

## Planned Technology Stack

| Layer | Planned Technologies |
| :--- | :--- |
| **Frontend** | React / Next.js (or Vite + React), TypeScript, Tailwind CSS |
| **Backend API** | Python, FastAPI, Uvicorn, Pydantic |
| **Computer Vision & Tracking** | OpenCV, Ultralytics YOLO (Object Detection), ByteTrack / DeepSORT (Tracking) |
| **Temporal & Contextual Reasoning** | Multimodal Vision-Language Models (VLMs) / LLMs, Temporal Event Pipeline |
| **Alerts & Localization** | Real-time WebSockets / SSE, English & Kannada Alert Generation |
| **Storage & Reporting** | Local Media Pipeline (`storage/`), JSON / SQLite Metadata, PDF / Markdown Report Generator |

---

## Project Structure

```text
NEMESIS-X/
├── frontend/             # Web dashboard for video upload, live alerts, evidence & reports
├── backend/              # FastAPI server, CV detection/tracking, temporal & VLM reasoning
├── storage/              # Local runtime workspace for media & generated outputs
│   ├── uploads/          # Raw incoming video files
│   ├── processed/        # Annotated videos and intermediate frame extractions
│   ├── evidence/         # Timestamped keyframes and anomaly clips
│   └── reports/          # Generated incident and video intelligence reports
├── docs/                 # Architecture diagrams, API specs, and hackathon documentation
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules for envs, caches, node_modules, and media
├── LICENSE               # Project license
└── README.md             # Project overview and roadmap
```

---

## Development Roadmap

- **Phase 1 — Foundation & Ingestion**
  - Establish project structure, environment configuration, and local storage pipeline.
  - Build video upload and frame-sampling endpoints in the backend.
- **Phase 2 — Detection, Tracking & Temporal Analysis**
  - Integrate object detection and persistent multi-object tracking across frames.
  - Implement temporal sliding-window analysis to identify unusual motion, loitering, or behavioral shifts.
- **Phase 3 — Contextual Reasoning & Bilingual Alerts**
  - Connect contextual VLM/LLM reasoning to validate anomalies and reduce false positives.
  - Generate real-time alerts in both **Kannada** and **English**.
- **Phase 4 — Evidence Extraction & Intelligent Reporting**
  - Capture timestamped visual evidence snapshots/clips in `storage/evidence/`.
  - Export structured incident reports into `storage/reports/`.
- **Phase 5 — Frontend Dashboard & Demo Polish**
  - Build interactive UI in `frontend/` for timeline playback, live bilingual alert feeds, evidence review, and report downloads.
  - End-to-end testing, latency tuning, and hackathon presentation readiness.
