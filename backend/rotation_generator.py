#!/usr/bin/env python3
"""Generate rotation schedule grids.

Two algorithms:
  **Cascade** (GCD(P, R) == 1): staggered handoff times so no two robots swap
  at once. Each robot's first shift is shortened by a cascade offset; all
  subsequent shifts are full-length (default 60 min).

  **Block rotation** (GCD(P, R) > 1): all robots swap simultaneously every
  `swap_min` minutes (default 45). After each full group cycle, robot
  assignments rotate left by 1 so every pilot touches every robot.

Usage:
    python rotation_generator.py 7 3 4                 # cascade
    python rotation_generator.py 6 3 3                 # block rotation
    python rotation_generator.py 6 3 3 --swap-min 45   # explicit swap
"""

from __future__ import annotations

import argparse
import math

SLOT_MINUTES = 15
MAX_ROBOT_SHIFT_SLOTS = 60 // SLOT_MINUTES  # 1 hour max on a robot
MIN_PILOT_ROBOT_RATIO = 4 / 3


def _validate_inputs(n_pilots: int, n_robots: int, n_tasks: int) -> None:
    assert n_pilots == n_robots + n_tasks, (
        f"n_pilots ({n_pilots}) must equal n_robots ({n_robots}) + n_tasks ({n_tasks})"
    )
    assert n_robots >= 1 and n_tasks >= 1 and n_pilots >= 2
    assert n_pilots / n_robots >= MIN_PILOT_ROBOT_RATIO, (
        f"pilot/robot ratio {n_pilots/n_robots:.2f} is below minimum "
        f"{MIN_PILOT_ROBOT_RATIO:.4f} — operators would get insufficient rest"
    )


def generate_cascade_grid(
    n_pilots: int,
    n_robots: int,
    n_tasks: int,
    shift_slots: int = 4,
    total_slots: int = 36,
) -> list[list[int | None]]:
    _validate_inputs(n_pilots, n_robots, n_tasks)
    assert shift_slots <= MAX_ROBOT_SHIFT_SLOTS, (
        f"shift_slots ({shift_slots} = {shift_slots * SLOT_MINUTES} min) exceeds "
        f"max robot shift ({MAX_ROBOT_SHIFT_SLOTS * SLOT_MINUTES} min)"
    )

    offsets = [math.ceil(shift_slots * (r + 1) / n_robots) for r in range(n_robots)]

    transitions: list[list[tuple[int, int]]] = [[] for _ in range(n_robots)]
    counter = 0
    robot_clock = [0] * n_robots

    while min(robot_clock) < total_slots:
        r = counter % n_robots
        p = counter % n_pilots
        duration = offsets[r] if len(transitions[r]) == 0 else shift_slots
        start = robot_clock[r]
        if start < total_slots:
            transitions[r].append((p, start))
        robot_clock[r] = start + duration
        counter += 1

    position: dict[int, tuple[str, int]] = {}
    for r in range(n_robots):
        position[transitions[r][0][0]] = ("robot", r)
    task_idx = 0
    for p in range(n_pilots):
        if p not in position:
            position[p] = ("task", task_idx)
            task_idx += 1

    all_swaps: list[tuple[int, int, int]] = []
    for r in range(n_robots):
        for p, t in transitions[r][1:]:
            all_swaps.append((t, r, p))
    all_swaps.sort()

    grid: list[list[int | None]] = []
    swap_idx = 0

    for t in range(total_slots):
        while swap_idx < len(all_swaps) and all_swaps[swap_idx][0] == t:
            _, r, new_p = all_swaps[swap_idx]
            old_p = next(p for p, pos in position.items() if pos == ("robot", r))
            vacated_task = position[new_p]
            assert vacated_task[0] == "task"
            position[new_p] = ("robot", r)
            position[old_p] = vacated_task
            swap_idx += 1

        slot: list[int | None] = [None] * (n_robots + n_tasks)
        for p, (kind, idx) in position.items():
            if kind == "robot":
                slot[idx] = p
            else:
                slot[n_robots + idx] = p
        grid.append(slot)

    return grid


def generate_block_rotation_grid(
    n_pilots: int,
    n_robots: int,
    n_tasks: int,
    swap_slots: int = 3,
    total_slots: int = 36,
) -> list[list[int | None]]:
    """Block rotation for GCD(P, R) > 1 cases.

    All robots swap simultaneously every `swap_slots` slots. After each full
    group cycle (robot group → task group → back), robot assignments rotate
    left by 1 so every pilot visits every robot position.
    """
    _validate_inputs(n_pilots, n_robots, n_tasks)
    assert swap_slots <= MAX_ROBOT_SHIFT_SLOTS, (
        f"swap_slots ({swap_slots} = {swap_slots * SLOT_MINUTES} min) exceeds "
        f"max robot shift ({MAX_ROBOT_SHIFT_SLOTS * SLOT_MINUTES} min)"
    )

    n_groups = n_pilots // n_robots
    assert n_groups >= 2, (
        f"block rotation needs n_pilots >= 2 * n_robots "
        f"(got {n_pilots} pilots, {n_robots} robots)"
    )

    groups: list[list[int]] = []
    for g in range(n_groups):
        groups.append(list(range(g * n_robots, g * n_robots + n_robots)))

    grid: list[list[int | None]] = []
    phase = 0

    while len(grid) < total_slots:
        rotation = (phase // n_groups) % n_robots
        group_idx = phase % n_groups

        robot_pilots = groups[group_idx][:]
        rotated = robot_pilots[-rotation:] + robot_pilots[:-rotation] if rotation else robot_pilots[:]

        task_pilots: list[int] = []
        for g in range(n_groups):
            if g == group_idx:
                continue
            gp = groups[g][:]
            rp = gp[-rotation:] + gp[:-rotation] if rotation else gp[:]
            task_pilots.extend(rp)

        for _ in range(swap_slots):
            if len(grid) >= total_slots:
                break
            slot: list[int | None] = [None] * (n_robots + n_tasks)
            for i, p in enumerate(rotated):
                slot[i] = p
            for i, p in enumerate(task_pilots):
                slot[n_robots + i] = p
            grid.append(slot)

        phase += 1

    return grid


def format_grid(
    grid: list[list[int | None]], n_robots: int, n_tasks: int,
) -> str:
    n_pilots = n_robots + n_tasks
    headers = [f"R{i}" for i in range(n_robots)] + [f"T{i}" for i in range(n_tasks)]
    lines = ["  Time  " + "  ".join(f"{h:>3}" for h in headers)]
    lines.append("  " + "-" * (8 + 5 * len(headers)))
    for t, slot in enumerate(grid):
        mins = t * SLOT_MINUTES
        h, m = divmod(mins, 60)
        cells = []
        for v in slot:
            cells.append(f" P{v}" if v is not None else "  .")
        lines.append(f"  {h:02d}:{m:02d}  " + "  ".join(f"{c:>3}" for c in cells))
    return "\n".join(lines)


def verify_grid(grid: list[list[int | None]], n_pilots: int, n_robots: int, n_tasks: int) -> list[str]:
    errors = []
    for t, slot in enumerate(grid):
        assigned = [v for v in slot if v is not None]
        if len(assigned) != n_pilots:
            errors.append(f"t={t}: only {len(assigned)}/{n_pilots} pilots assigned")
        if len(set(assigned)) != len(assigned):
            errors.append(f"t={t}: duplicate pilot assignment {assigned}")
        for v in assigned:
            if v < 0 or v >= n_pilots:
                errors.append(f"t={t}: invalid pilot index {v}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a rotation schedule grid")
    parser.add_argument("n_pilots", type=int)
    parser.add_argument("n_robots", type=int)
    parser.add_argument("n_tasks", type=int)
    parser.add_argument("--shift-min", type=int, default=60,
                        help="Robot shift duration for cascade mode (default 60)")
    parser.add_argument("--swap-min", type=int, default=45,
                        help="Robot swap duration for block rotation mode (default 45)")
    parser.add_argument("--total-hours", type=float, default=9,
                        help="Total schedule hours (default 9)")
    parser.add_argument("--name", type=str, default=None, help="Schedule label (default: auto)")
    args = parser.parse_args()

    total_slots = int(args.total_hours * 60 / SLOT_MINUTES)
    use_block = args.n_pilots % args.n_robots == 0

    if use_block:
        assert args.swap_min % SLOT_MINUTES == 0, (
            f"swap-min must be a multiple of {SLOT_MINUTES}"
        )
        swap_slots = args.swap_min // SLOT_MINUTES
        algo = "Block Rotation"
        name = args.name or f"{args.n_pilots}P-{args.n_robots}R-{args.n_tasks}T {algo}"

        print(f"Generating: {name}")
        print(f"  {args.n_pilots} pilots, {args.n_robots} robots, {args.n_tasks} tasks")
        print(f"  Algorithm: {algo} (GCD={math.gcd(args.n_pilots, args.n_robots)})")
        print(f"  Swap: {args.swap_min} min ({swap_slots} slots), "
              f"Total: {args.total_hours}h ({total_slots} slots)")
        print()

        grid = generate_block_rotation_grid(
            args.n_pilots, args.n_robots, args.n_tasks, swap_slots, total_slots,
        )
    else:
        assert args.shift_min % SLOT_MINUTES == 0, (
            f"shift-min must be a multiple of {SLOT_MINUTES}"
        )
        shift_slots = args.shift_min // SLOT_MINUTES
        algo = "Cascade"
        name = args.name or f"{args.n_pilots}P-{args.n_robots}R-{args.n_tasks}T {algo}"

        print(f"Generating: {name}")
        print(f"  {args.n_pilots} pilots, {args.n_robots} robots, {args.n_tasks} tasks")
        print(f"  Algorithm: {algo} (P%R≠0, GCD={math.gcd(args.n_pilots, args.n_robots)})")
        print(f"  Shift: {args.shift_min} min ({shift_slots} slots), "
              f"Total: {args.total_hours}h ({total_slots} slots)")
        offsets = [math.ceil(shift_slots * (r + 1) / args.n_robots) for r in range(args.n_robots)]
        print(f"  Initial offsets: {[o * SLOT_MINUTES for o in offsets]} min")
        print()

        grid = generate_cascade_grid(
            args.n_pilots, args.n_robots, args.n_tasks, shift_slots, total_slots,
        )

    errors = verify_grid(grid, args.n_pilots, args.n_robots, args.n_tasks)
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  {e}")
        return

    print(format_grid(grid, args.n_robots, args.n_tasks))
    print(f"\n  Grid: {len(grid)} slots, all {args.n_pilots} pilots assigned every slot. ✓")


if __name__ == "__main__":
    main()
