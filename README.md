# NEMESIS-X

NEMESIS-X is a video intelligence application for analyzing recorded footage and live webcam sessions. It combines object detection and tracking with temporal events, evidence review, and investigation tools.

## Features

- **Video analysis:** Detect and track objects in uploaded recordings, with timestamped detections and evidence.
- **Live monitoring:** Analyze webcam sessions and display current detections and events.
- **Behaviour intelligence:** Review movement patterns, repeated interactions, explainable anomaly scores, and session-scoped baselines.
- **Smart zones:** Define normalized polygon zones and review confirmed entries, exits, and time-in-zone events.
- **Investigation workspace:** Link existing analyses and completed live sessions; review timelines, track relationships, evidence, and private notes.
- **Intelligent search and labels:** Search stored video intelligence and display detection classes, tracking IDs, and confidence on frames.
- **Persistent anonymous identities:** Compare appearance descriptors within one analysis or live session. This does not identify real-world people or match identities across videos.
- **Playback compatibility:** Create a separate browser-compatible playback copy when a source video codec is unsupported; the original upload is preserved.
- **Kannada and English notifications:** Use the available voice notification features and saved preferences.

## Technology

| Area | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy |
| Video intelligence | OpenCV, Ultralytics YOLO, ByteTrack |
| Database | SQLite by default |
| Authentication | JWT bearer tokens |

## Requirements

- Python 3.10 or later
- Node.js 20.19+ or 22.12+
- npm
- A webcam for live monitoring

The backend defaults to CPU inference. The YOLO weights may be downloaded the first time a model is used.

## Setup

Clone the repository:

```bash
git clone https://github.com/Chandanaa-003/NEMESIS-X.git
cd NEMESIS-X
```

### Backend

In PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

If PowerShell prevents virtual environment activation, either allow local scripts for your user or run the environment's Python directly, for example `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

On macOS or Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
test -f .env || cp .env.example .env
```

The backend reads configuration from `backend/.env`. The defaults use SQLite and local storage. Before exposing the application beyond local development, set a private `SECRET_KEY`, review CORS origins, and configure storage appropriately. Do not commit `.env` files or credentials.

### Frontend

Open a second terminal at the repository root:

```bash
cd frontend
npm install
npm run dev
```

The frontend defaults to the API at `http://127.0.0.1:8000/api/v1`. To use another backend URL, set `VITE_API_BASE_URL` before starting Vite, for example in PowerShell:

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
npm run dev
```

## Run the application

Start the backend from the `backend` directory:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend from the `frontend` directory in another terminal:

```bash
npm run dev
```

Open:

- Frontend: <http://127.0.0.1:5173>
- API health: <http://127.0.0.1:8000/api/v1/health>
- Interactive API documentation: <http://127.0.0.1:8000/docs>

The backend initializes the database schema on startup. By default, its SQLite database and media are stored locally; keep backups of data you want to retain.

## Tests and checks

Run backend tests from `backend`:

```bash
python -m pip install pytest
python -m pytest tests -q
```

Run frontend checks from `frontend`:

```bash
npm run lint
npm run build
```

## API areas

The API is versioned under `/api/v1`. Interactive endpoint details are available at `/docs`. Main areas include:

- `/auth` — account and token operations
- `/videos` and `/analysis` — uploads, recorded analysis, and event discovery
- `/live` — webcam monitoring
- `/behavior` and `/zones` — behaviour reports and zone configuration/activity
- `/investigations` — investigations, timelines, evidence references, and notes
- `/search` and `/identities` — intelligence search and source-scoped anonymous identities

Most analysis and evidence routes require authentication and enforce ownership of the related video or live session.

## Important limitations

- Person and object identity labels are anonymous and scoped to a single recording or live session. Appearance similarity is not proof of identity; facial recognition and cross-camera identity matching are not implemented.
- Movement estimates use image coordinates. They are not physical speeds unless camera calibration is available.
- Live investigation data is limited to persisted events, snapshots, and track samples; continuous live video is not necessarily retained.
- Anomaly and behaviour scores are explainable rule-based indicators, not determinations of intent or a trained statistical model.
- Browser-compatible playback is stored separately from the original upload.

## Project layout

```text
NEMESIS-X/
├── backend/
│   ├── app/          # FastAPI routes, models, services, and workers
│   ├── tests/        # Backend tests
│   ├── weights/      # Local model weights
│   ├── .env.example  # Backend configuration template
│   └── requirements.txt
├── frontend/
│   └── src/          # React application
├── storage/          # Local uploads, evidence, and generated media
├── docs/             # Project documentation
└── README.md
```

## License

See [LICENSE](LICENSE).
