# NEMESIS-X

**Contextual AI Video Intelligence for Real-Time Anomaly Detection, Bilingual Alerts & Automated Evidence Reporting**

---

## Objective

NEMESIS-X is an AI-powered video intelligence system designed to detect unusual events through multi-stage **object detection**, **multi-object tracking**, **temporal analysis**, and **contextual reasoning**. Rather than relying solely on isolated frame classifications, NEMESIS-X understands how scenes evolve over time to surface meaningful anomalies and produce:

- **Timestamped Visual Evidence** — Annotated keyframes and video clips capturing detected events.
- **Real-Time Bilingual Alerts** — Actionable notifications delivered in both **Kannada** and **English**.
- **Intelligent Video Reports** — Structured incident summaries with context, severity, timelines, and supporting evidence.

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
