# Robot Lab Schedule Manager

Web app for building and managing robot lab shift schedules. FastAPI backend + React/TypeScript frontend.

## Routes

| Path | Description |
|------|-------------|
| `/schedule` | Home — six shift/day entry cards (Shift 1–3 × Today/Tomorrow) |
| `/schedule/roster` | Operator roster management per shift |
| `/schedule/shift/:shift/:day` | Schedule editor — robot view (editable, autosave) + read-only pilot view |
| `/` | Redirects to `/schedule` |

## Stack

- **Backend**: FastAPI + SQLite (no database server to run)
- **Frontend**: React 19 + Vite + TypeScript + React Router

## Data storage

All data lives in a single local SQLite file at `backend/schedule.db`, created
automatically on first run — there is nothing to provision or migrate. Tables are
created on demand in code (see `ensure_*_table` in `backend/schedule_api.py` and
`backend/roster_api.py`).

## Environment

No `.env` is required. Copy `backend/.env.example` to `backend/.env` only to override a
default:

```env
SCHEDULE_DATABASE_URL=./schedule.db   # optional; path or sqlite:/// URL for the DB file
EDIT_PASSWORD=your-password-here       # optional; enables edit mode in the UI
```

## Run (development)

Quickest path — runs both servers with hot reload:

```bash
./start.sh
```

Or run them separately.

**Backend** (Python 3.12+):

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

Or with a plain venv:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/schedule`.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/auth/unlock` | Unlock edit mode (body: `{"password": "..."}`) |
| `POST` | `/api/schedule/generate` | Generate a rotation grid on the fly (cascade or block rotation) |
| `GET` | `/api/schedule/{shift}/{day}` | Get shift schedule (`shift` 1–3, `day` today/tomorrow) |
| `PUT` | `/api/schedule/{shift}/{day}` | Save shift schedule |
| `GET` | `/api/roster` | List operators (optional `?shift=1`) |
| `POST` | `/api/roster` | Add operator |
| `PATCH` | `/api/roster/{id}` | Update operator |
| `DELETE` | `/api/roster/{id}` | Delete operator |
