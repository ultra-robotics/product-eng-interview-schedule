from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Literal

from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent


def _load_backend_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    path = _BACKEND_DIR / ".env"
    if path.is_file():
        load_dotenv(path, override=True)


_load_backend_dotenv()

import db  # noqa: E402

from availability_service import confirm_assignments  # noqa: E402

from schedule_api import (  # noqa: E402
    GenerateRequest,
    GenerateResponse,
    ScheduleDocument,
    default_document,
    ensure_schedule_table,
    generate_schedule_grid,
    get_schedule,
    put_schedule,
    slot_key,
)


class Settings(BaseSettings):
    schedule_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SCHEDULE_DATABASE_URL", "schedule_database_url"),
    )

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app = FastAPI(title="Schedule Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "SCHEDULE_DATABASE_URL is invalid. It is optional — the app uses a "
                f"local SQLite file by default. To override, set it in "
                f"{_BACKEND_DIR / '.env'} (see .env.example)."
            ),
        ) from e


FRONTEND_DIST_DIR = _BACKEND_DIR.parent / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"


def _mount_frontend_assets_if_present() -> None:
    if FRONTEND_ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS_DIR)), name="assets")


_mount_frontend_assets_if_present()


def get_schedule_database_url() -> str | None:
    """Path/URL of the SQLite schedule DB. Falls back to backend/schedule.db."""
    s = get_settings()
    if s.schedule_database_url and s.schedule_database_url.strip():
        return s.schedule_database_url.strip()
    return None


@contextmanager
def schedule_conn():
    conn = db.connect(get_schedule_database_url())
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class UnlockRequest(BaseModel):
    password: str


@app.post("/api/auth/unlock")
def auth_unlock(body: UnlockRequest) -> dict[str, bool]:
    expected = os.environ.get("EDIT_PASSWORD", "password")
    assert expected, "EDIT_PASSWORD env var not set on server"
    return {"ok": body.password == expected}


@app.post("/api/schedule/generate", response_model=GenerateResponse)
def api_generate_schedule(body: GenerateRequest) -> GenerateResponse:
    try:
        return generate_schedule_grid(body)
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/schedule/{shift}/{day}")
def api_get_schedule(
    shift: int,
    day: Literal["today", "tomorrow"],
) -> dict:
    if shift not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="shift must be 1, 2, or 3")
    sk = slot_key(shift, day)
    try:
        with schedule_conn() as conn:
            ensure_schedule_table(conn)
            doc = get_schedule(conn, sk)
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error: {e}",
        ) from e
    out = doc.model_copy(update={"slot_key": sk})
    return out.model_dump(mode="json")


@app.put("/api/schedule/{shift}/{day}")
def api_put_schedule(
    shift: int,
    day: Literal["today", "tomorrow"],
    body: ScheduleDocument,
) -> dict[str, str]:
    if shift not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="shift must be 1, 2, or 3")
    sk = slot_key(shift, day)
    doc = body.model_copy(update={"slot_key": sk})
    # Confirm assigned pilots are still available in the roster system before we
    # persist this slot (source of truth for availability lives off-box).
    confirm_assignments(doc)
    try:
        with schedule_conn() as conn:
            ensure_schedule_table(conn)
            put_schedule(conn, doc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error: {e}",
        ) from e
    return {"ok": "true", "slot_key": sk}


@app.get("/")
def frontend_root() -> FileResponse:
    index = FRONTEND_DIST_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Frontend build not found at frontend/dist/index.html. "
                "Build frontend before running production server."
            ),
        )
    return FileResponse(str(index))


@app.get("/{full_path:path}")
def frontend_routes(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = FRONTEND_DIST_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Frontend build not found at frontend/dist/index.html. "
                "Build frontend before running production server."
            ),
        )
    return FileResponse(str(index))


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RAILWAY_ENVIRONMENT") is None,
    )


if __name__ == "__main__":
    main()
