#!/usr/bin/env python3
"""Seed the schedule_slots table with realistic example data for today + tomorrow.

Run from backend/:
    python seed_data.py

Idempotent — uses put_schedule's upsert, so re-running overwrites the same
slots rather than duplicating. start.sh runs this once on first launch (when
schedule.db doesn't exist yet).

Uses SCHEDULE_DATABASE_URL if set, otherwise the default backend/schedule.db.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

import db
from schedule_api import (
    DEFAULT_DAY_END,
    DEFAULT_DAY_START,
    ScheduleDocument,
    ScheduleGroup,
    SchedulePilot,
    ensure_schedule_table,
    put_schedule,
    slot_key,
    time_slot_count,
)

BACKEND_DIR = Path(__file__).resolve().parent

# A distinct color per pilot slot (kept consistent across groups).
PALETTE = ["#2563EB", "#DC2626", "#16A34A", "#D97706"]

ROBOTS = ["Robot Alpha", "Robot Beta"]
TASKS = ["Inspection", "Packaging"]

# Per-shift pilot names (4 pilots = 2 robots + 2 tasks per group).
SHIFT_PILOTS: dict[int, list[str]] = {
    1: ["Ava Patel", "Ben Carter", "Chloe Kim", "Diego Ramos"],
    2: ["Elena Novak", "Frank Obi", "Grace Lin", "Hiro Tanaka"],
    3: ["Ines Soto", "Jack Reed", "Kira Volkov", "Leo Mensah"],
}

SWAP_SLOTS = 8  # rotate assignments every 8 slots (2 hours at 15-min slots)
LUNCH_SLOTS = range(24, 28)  # 12:00–13:00 everyone on break (cells -> None)


def build_group(names: list[str], offset: int) -> ScheduleGroup:
    """One group: pilots rotate across robot/task rows over the day."""
    n_rows = len(ROBOTS) + len(TASKS)
    assert n_rows == len(names), "rows must equal pilot count"

    pilots = [
        SchedulePilot(id=f"p{i+1}", name=name, color_hex=PALETTE[i])
        for i, name in enumerate(names)
    ]
    pilot_ids = [p.id for p in pilots]
    n_slots = time_slot_count(DEFAULT_DAY_START, DEFAULT_DAY_END)

    grid: list[list[str | None]] = []
    for t in range(n_slots):
        if t in LUNCH_SLOTS:
            grid.append([None] * n_rows)
            continue
        rotation = (t // SWAP_SLOTS) + offset
        grid.append([pilot_ids[(j + rotation) % n_rows] for j in range(n_rows)])

    return ScheduleGroup(
        id="line-a",
        name="Line A",
        robot_labels=list(ROBOTS),
        task_labels=list(TASKS),
        pilots=pilots,
        grid=grid,
    )


def build_document(sk: str, names: list[str], offset: int) -> ScheduleDocument:
    return ScheduleDocument(
        slot_key=sk,
        day_start=DEFAULT_DAY_START,
        day_end=DEFAULT_DAY_END,
        groups=[build_group(names, offset)],
    )


def get_db_url() -> str | None:
    env_file = dotenv_values(BACKEND_DIR / ".env")
    url = (os.environ.get("SCHEDULE_DATABASE_URL") or env_file.get("SCHEDULE_DATABASE_URL") or "").strip()
    return url or None


def main() -> None:
    conn = db.connect(get_db_url())
    try:
        ensure_schedule_table(conn)
        count = 0
        for day, offset in (("today", 0), ("tomorrow", 1)):
            for shift, names in SHIFT_PILOTS.items():
                sk = slot_key(shift, day)
                doc = build_document(sk, names, offset)
                put_schedule(conn, doc)
                count += 1
                print(f"  seeded {sk}  ({len(doc.groups[0].pilots)} pilots, {len(doc.groups[0].grid)} slots)")
        print(f"Done. Seeded {count} schedule slots (3 shifts x today/tomorrow).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
