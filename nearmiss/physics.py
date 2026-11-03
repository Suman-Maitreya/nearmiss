"""Phase 2: calibration (homography + holdout), ground-contact extraction,
trajectory smoothing, grid occupancy, visit segmentation, PET.

Implements Architecture 2.1 §8.6-8.9 grid-based PET.
Vehicles are inflated to oriented rectangles using length/width/course.
Pedestrians and other point-mass agents are treated as single cells.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Iterable


# --- Config defaults (match config.yaml) ---
CELL_SIZE_M = 0.5
VISIT_GAP_MAX_S = 0.5
PET_CANDIDATE_MAX_S = 2.0
CELL_NEIGHBOR_RADIUS = 1

# agents inflated as rectangles (uses length_med/width_med/course)
VEHICLE_TYPES = {'car','truck','trailer','van','bus','tricycle'}
# point-mass agents (single cell, maybe +neighbors)
POINT_TYPES = {'pedestrian','moped'}  # moped is small; treat as point for now


def to_cell(x_m: float, y_m: float, cell_size_m: float = CELL_SIZE_M) -> tuple[int, int]:
    return (int(np.floor(x_m / cell_size_m)), int(np.floor(y_m / cell_size_m)))


def rect_cells(cx: float, cy: float, length_m: float, width_m: float,
               course_deg: float, cell_size_m: float = CELL_SIZE_M) -> set[tuple[int,int]]:
    """Return the set of grid cells covered by an oriented rectangle.

    cx,cy = center (metres). length_m along heading, width_m perpendicular.
    course_deg = heading in degrees (0 = +X axis, 90 = +Y).

    Samples a dense grid of points inside the rectangle and quantizes.
    """
    if length_m <= 0 or width_m <= 0:
        return {to_cell(cx, cy, cell_size_m)}
    # sample at half-cell resolution
    step = cell_size_m / 2
    n_l = max(2, int(np.ceil(length_m / step)) + 1)
    n_w = max(2, int(np.ceil(width_m / step)) + 1)
    ls = np.linspace(-length_m/2, length_m/2, n_l)
    ws = np.linspace(-width_m/2, width_m/2, n_w)
    L, W = np.meshgrid(ls, ws, indexing='ij')
    theta = np.deg2rad(course_deg)
    xs = cx + L*np.cos(theta) - W*np.sin(theta)
    ys = cy + L*np.sin(theta) + W*np.cos(theta)
    cells = set()
    for x, y in zip(xs.ravel(), ys.ravel()):
        cells.add(to_cell(x, y, cell_size_m))
    return cells


@dataclass
class Visit:
    track_id: int
    cell: tuple[int, int]
    enter_t: float
    exit_t: float


def build_visits(
    df_track: pd.DataFrame,
    cell_size_m: float = CELL_SIZE_M,
    gap_max_s: float = VISIT_GAP_MAX_S,
    use_footprint: bool = True,
) -> list[Visit]:
    """Convert one track into Visits.

    When use_footprint=True and df_track has length_med/width_med/course, a
    vehicle's position-at-time emits one visit per cell its rectangle covers.
    Pedestrians and other point-mass types use centroid cell only.

    df_track must have columns: id, time, cx_m, cy_m, type.
    Optional (used for footprint): length_med, width_med, course.
    """
    if len(df_track) == 0:
        return []

    df = df_track.sort_values('time').reset_index(drop=True)
    tid = int(df['id'].iloc[0])
    agent_type = str(df['type'].iloc[0])
    times = df['time'].to_numpy()

    inflate = (use_footprint
               and agent_type in VEHICLE_TYPES
               and {'length_med','width_med','course'}.issubset(df.columns))

    # Compute cell(s) at each timestamp.
    # For point agents, 1 cell per timestamp; for vehicles, N cells per timestamp.
    # We represent visits per (cell, track) as (enter_t, exit_t) spans.
    # Approach: walk timeline; for each cell that becomes "entered" at t,
    # keep updating exit_t while that cell stays in the agent's footprint
    # across contiguous timestamps (gap_max_s rule).
    open_visits: dict[tuple[int,int], tuple[float,float]] = {}  # cell -> (enter_t, last_t)
    all_visits: list[Visit] = []

    for i in range(len(df)):
        t = times[i]
        if inflate:
            L = float(df['length_med'].iloc[i])
            W = float(df['width_med'].iloc[i])
            C = float(df['course'].iloc[i])
            if not (np.isfinite(L) and np.isfinite(W) and np.isfinite(C) and L>0 and W>0):
                cells_t = {to_cell(float(df['cx_m'].iloc[i]), float(df['cy_m'].iloc[i]), cell_size_m)}
            else:
                cells_t = rect_cells(float(df['cx_m'].iloc[i]), float(df['cy_m'].iloc[i]), L, W, C, cell_size_m)
        else:
            cells_t = {to_cell(float(df['cx_m'].iloc[i]), float(df['cy_m'].iloc[i]), cell_size_m)}

        # close visits whose cell is NOT in cells_t or where gap too large
        to_close = []
        for cell, (enter_t, last_t) in open_visits.items():
            if cell not in cells_t or (t - last_t) > gap_max_s:
                to_close.append(cell)
        for cell in to_close:
            enter_t, last_t = open_visits.pop(cell)
            all_visits.append(Visit(tid, cell, enter_t, last_t))

        # open/extend visits for cells_t
        for cell in cells_t:
            if cell in open_visits:
                enter_t, _ = open_visits[cell]
                open_visits[cell] = (enter_t, t)
            else:
                open_visits[cell] = (t, t)

    for cell, (enter_t, last_t) in open_visits.items():
        all_visits.append(Visit(tid, cell, enter_t, last_t))

    return all_visits


def _neighbor_cells(cell: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    cx, cy = cell
    return [(cx + dx, cy + dy) for dx in range(-radius, radius+1) for dy in range(-radius, radius+1)]


def pet_between(
    visits_a: list[Visit],
    visits_b: list[Visit],
    candidate_max_s: float = PET_CANDIDATE_MAX_S,
    neighbor_radius: int = CELL_NEIGHBOR_RADIUS,
) -> float | None:
    by_cell_a: dict[tuple[int,int], list[Visit]] = {}
    for v in visits_a:
        by_cell_a.setdefault(v.cell, []).append(v)

    best: float | None = None
    for vb in visits_b:
        for nb in _neighbor_cells(vb.cell, neighbor_radius):
            for va in by_cell_a.get(nb, []):
                if va.enter_t <= vb.exit_t and vb.enter_t <= va.exit_t:
                    return 0.0
                if vb.enter_t > va.exit_t:
                    delta = vb.enter_t - va.exit_t
                else:
                    delta = va.enter_t - vb.exit_t
                if 0 <= delta <= candidate_max_s:
                    if best is None or delta < best:
                        best = delta
    return best


def pairwise_pet(
    traj: pd.DataFrame,
    pair_ids: Iterable[tuple[int, int]],
    cell_size_m: float = CELL_SIZE_M,
    gap_max_s: float = VISIT_GAP_MAX_S,
    candidate_max_s: float = PET_CANDIDATE_MAX_S,
    neighbor_radius: int = CELL_NEIGHBOR_RADIUS,
    use_footprint: bool = True,
) -> dict[tuple[int, int], float | None]:
    needed = set()
    for a, b in pair_ids:
        needed.add(a); needed.add(b)
    sub = traj[traj['id'].isin(needed)]
    visits_by_id: dict[int, list[Visit]] = {}
    for tid, grp in sub.groupby('id'):
        visits_by_id[int(tid)] = build_visits(grp, cell_size_m, gap_max_s, use_footprint)
    out = {}
    for a, b in pair_ids:
        va = visits_by_id.get(int(a), [])
        vb = visits_by_id.get(int(b), [])
        out[(a, b)] = pet_between(va, vb, candidate_max_s, neighbor_radius)
    return out
