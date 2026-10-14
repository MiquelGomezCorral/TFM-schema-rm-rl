"""The last step of the graph layout: clear states off edges and place the wells.

States are circles joined by straight edges. After the layers are placed, this module slides
states until none is near an edge it is not part of, no edge label lies on a state, and labels
overlap less, trims crossings, and puts each well in a lane left of the main flow. The cost
functions work on numpy arrays so that every candidate position of a state is scored at once.
"""

from dataclasses import dataclass

import numpy as np

from src.config import GraphStyle

_GRAPH = GraphStyle()
_RADIUS = _GRAPH.node_diameter / 2

# Geometry: how far a straight edge keeps from a state's centre, and what counts as clear.
CLEARANCE = _RADIUS + 12  # the aim
TOLERANCE = 5.0  # a shortfall this small is accepted: the edge still clears a state's rim
_LEVEL = 1.0  # states this close in height count as level

# Settling: a state moves in steps along its rank, and a move is judged by its cost.
_NUDGE_STEP = 8
_NUDGE_REACH = 100  # a state may move this many steps either way in one move
_NUDGES = 400  # repair moves in one go
_SWEEPS = 6  # repair-and-polish rounds
_MIN_GAIN = 0.5  # a polish move must save at least this much
_SHORT_WEIGHT = 20.0  # a shortfall outweighs the soft wishes below
_CHIP_WEIGHT = 2.0  # a state under an edge's label chip costs less than one on the edge
_CHIP_OVERLAP_WEIGHT = 3.0  # per unit of width two label chips share
_CROSS_COST = 60.0  # one crossing between two edges
_LENGTH_WEIGHT = 0.001  # per squared horizontal reach of an edge, so edges stay short

# Wells: a lane left of the main flow.
_LANE_MARGIN = _GRAPH.node_gap * 3 / 4  # a well keeps this far left of the main states


@dataclass
class _Field:
    """The states as arrays: where each sits, which are wells, and the edges between them."""

    names: list[str]
    x: np.ndarray
    y: np.ndarray
    well: np.ndarray
    home: np.ndarray  # the height a well prefers; unused for other states
    src: np.ndarray
    dst: np.ndarray
    half: np.ndarray  # half the width of each edge's label chip
    lift: np.ndarray  # how far each label sits below the middle of its edge
    top: float
    bottom: float


def _field(
    positions: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    preferred: dict[str, float],
    chips: dict[tuple[str, str], tuple[float, float]],
) -> _Field:
    names = list(positions)
    index = {name: slot for slot, name in enumerate(names)}
    y = np.array([positions[name][1] for name in names], dtype=float)
    main = [slot for slot, name in enumerate(names) if name not in preferred]
    return _Field(
        names,
        np.array([positions[name][0] for name in names], dtype=float),
        y,
        np.array([name in preferred for name in names]),
        np.array([preferred.get(name, 0.0) for name in names]),
        np.array([index[source] for source, _ in edges], dtype=int),
        np.array([index[target] for _, target in edges], dtype=int),
        np.array([chips[edge][0] for edge in edges], dtype=float),
        np.array([chips[edge][1] for edge in edges], dtype=float),
        float(y[main].min()) if main else 0.0,
        float(y[main].max()) if main else 0.0,
    )


def settle(
    positions: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    preferred: dict[str, float],
    chips: dict[tuple[str, str], tuple[float, float]],
) -> float:
    """Move states until none is near an edge it is not part of and fewer edges cross.

    Positions change in place. Return the largest shortfall left, which is within the
    tolerance when every state clears every edge.

    A repair takes the state with the largest shortfall and moves it, or an end of its worst
    edge, to the spot that costs least; when that does not help, any state may move. A polish
    sweep then lets each state take its cheapest spot. A main state slides along its rank; a
    well also moves up or down its lane. Cost counts shortfalls, crossings, long edges,
    crowding, and a well drifting from its height or its lane.
    """
    if not edges:
        return 0.0
    field = _field(positions, edges, preferred, chips)
    reach = np.arange(-_NUDGE_REACH, _NUDGE_REACH + 1) * _NUDGE_STEP
    for _ in range(_SWEEPS):
        _repair(field, reach)
        if not _polish(field, reach):
            break
    _repair(field, reach)

    positions.update(
        {name: (float(field.x[i]), float(field.y[i])) for i, name in enumerate(field.names)}
    )
    return float(_shortfalls(field).max())


def _repair(field: _Field, reach: np.ndarray) -> None:
    for _ in range(_NUDGES):
        shortfalls = _shortfalls(field)
        worst = shortfalls.max(axis=0)
        if worst.max() <= TOLERANCE:
            return
        state = int(worst.argmax())
        edge = int(shortfalls[:, state].argmax())
        gain, mover, x, y = _best_move(field, {state, field.src[edge], field.dst[edge]}, reach)
        if gain >= 0:
            return
        field.x[mover], field.y[mover] = x, y


def _polish(field: _Field, reach: np.ndarray) -> bool:
    """Let each state in turn take its cheapest spot; say whether any of them moved."""
    moved = False
    for state in range(len(field.x)):
        gain, mover, x, y = _best_move(field, [state], reach)
        if gain < -_MIN_GAIN:
            field.x[mover], field.y[mover] = x, y
            moved = True
    return moved


def _best_move(field: _Field, movers, reach: np.ndarray) -> tuple[float, int, float, float]:
    """Return (cost change, mover, x, y) of the cheapest move among the movers' spots."""
    moves = []
    for mover in movers:
        x, y = field.x[mover], field.y[mover]
        slides = [(x + reach, np.full(len(reach), y))]
        if field.well[mover]:
            slides.append((np.full(len(reach), x), y + reach))
        for xs, ys in slides:
            costs = _move_costs(field, int(mover), xs, ys)
            best = costs.argmin()
            moves.append((costs[best] - costs[_NUDGE_REACH], int(mover), xs[best], ys[best]))
    return min(moves)


def _shortfalls(field: _Field) -> np.ndarray:
    """Return an edges-by-states matrix of how far each state is inside an edge's clearance.

    Only states level with or between an edge's ends count, and never the ends themselves.
    """
    ax, ay = field.x[field.src][:, None], field.y[field.src][:, None]
    bx, by = field.x[field.dst][:, None], field.y[field.dst][:, None]
    distance = _segment_distance((field.x[None, :], field.y[None, :]), (ax, ay), (bx, by))
    between = (field.y[None, :] >= np.minimum(ay, by) - _LEVEL) & (
        field.y[None, :] <= np.maximum(ay, by) + _LEVEL
    )
    slots = np.arange(len(field.x))[None, :]
    inner = between & (slots != field.src[:, None]) & (slots != field.dst[:, None])
    return np.where(inner, np.maximum(CLEARANCE - distance, 0.0), 0.0)


def _move_costs(field: _Field, mover: int, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Cost of putting ``mover`` at each candidate spot, counting only terms it affects."""
    x, y = field.x, field.y
    others = np.array([state for state in range(len(x)) if state != mover])
    at = np.flatnonzero((field.src == mover) | (field.dst == mover))
    far = np.where(field.src[at] == mover, field.dst[at], field.src[at])

    # The mover near an edge it is not an end of, for edges level with it.
    apart = np.flatnonzero((field.src != mover) & (field.dst != mover))
    ax, ay = x[field.src[apart]][:, None], y[field.src[apart]][:, None]
    bx, by = x[field.dst[apart]][:, None], y[field.dst[apart]][:, None]
    gap = _segment_distance((xs[None, :], ys[None, :]), (ax, ay), (bx, by))
    level = (ys[None, :] >= np.minimum(ay, by) - _LEVEL) & (
        ys[None, :] <= np.maximum(ay, by) + _LEVEL
    )
    cost = _SHORT_WEIGHT * (np.where(level, _short(gap), 0.0) ** 2).sum(axis=0)

    # Other states near an edge at the mover, whose far end stays put.
    px, py = x[others][None, :, None], y[others][None, :, None]
    tx, ty = x[far][:, None, None], y[far][:, None, None]
    gap = _segment_distance((px, py), (xs[None, None, :], ys[None, None, :]), (tx, ty))
    level = (py >= np.minimum(ys[None, None, :], ty) - _LEVEL) & (
        py <= np.maximum(ys[None, None, :], ty) + _LEVEL
    )
    counted = level & (others[None, :, None] != far[:, None, None])
    cost += _SHORT_WEIGHT * (np.where(counted, _short(gap), 0.0) ** 2).sum(axis=(0, 1))

    cost += _chip_costs(field, mover, xs, ys)
    cost += _CROSS_COST * _crossings_at(field, mover, far, xs, ys)
    cost += _LENGTH_WEIGHT * ((xs[None, :] - x[far][:, None]) ** 2).sum(axis=0)
    cost += _crowding(field, mover, others, xs, ys)
    if field.well[mover]:
        cost += 0.02 * (ys - field.home[mover]) ** 2
        cost += 0.5 * (np.maximum(field.top - ys, 0) + np.maximum(ys - field.bottom, 0)) ** 2
    return cost + 1e-4 * ((xs - x[mover]) ** 2 + (ys - y[mover]) ** 2)


def _chip_costs(field: _Field, mover: int, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Cost of label chips lying on states.

    The mover on other edges' chips, and the chips of the mover's edges on every state,
    the mover and the far end of the edge included: a short edge between two states is
    covered by its own label.
    """
    x, y = field.x, field.y
    others = np.array([state for state in range(len(x)) if state != mover])
    at = np.flatnonzero((field.src == mover) | (field.dst == mover))
    far = np.where(field.src[at] == mover, field.dst[at], field.src[at])
    apart = np.flatnonzero((field.src != mover) & (field.dst != mover))
    gap = _chip_gap(
        (xs[None, :], ys[None, :]),
        ((x[field.src[apart]] + x[field.dst[apart]]) / 2)[:, None],
        ((y[field.src[apart]] + y[field.dst[apart]]) / 2 + field.lift[apart])[:, None],
        field.half[apart][:, None],
    )
    cost = (_chip_short(gap) ** 2).sum(axis=0)

    tx, ty = x[far][:, None], y[far][:, None]
    centre_x = (xs[None, :] + tx) / 2
    centre_y = (ys[None, :] + ty) / 2 + field.lift[at][:, None]
    gap = _chip_gap((xs[None, :], ys[None, :]), centre_x, centre_y, field.half[at][:, None])
    cost += (_chip_short(gap) ** 2).sum(axis=0)
    gap = _chip_gap(
        (x[others][None, :, None], y[others][None, :, None]),
        centre_x[:, None, :],
        centre_y[:, None, :],
        field.half[at][:, None, None],
    )
    cost = _CHIP_WEIGHT * (cost + (_chip_short(gap) ** 2).sum(axis=(0, 1)))

    # The mover's chips lying on the chips of edges that do not touch it.
    overlap_x = (
        field.half[at][:, None, None]
        + field.half[apart][None, :, None]
        - np.abs(
            centre_x[:, None, :] - ((x[field.src[apart]] + x[field.dst[apart]]) / 2)[None, :, None]
        )
    )
    overlap_y = _GRAPH.label_height - np.abs(
        centre_y[:, None, :]
        - ((y[field.src[apart]] + y[field.dst[apart]]) / 2 + field.lift[apart])[None, :, None]
    )
    overlap = np.maximum(overlap_x, 0.0) * np.maximum(overlap_y, 0.0) / _GRAPH.label_height
    return cost + _CHIP_OVERLAP_WEIGHT * overlap.sum(axis=(0, 1))


def _chip_gap(point, centre_x, centre_y, half_width):
    """Distance from points to label chips: rectangles half_width wide and one chip tall."""
    beyond_x = np.maximum(np.abs(point[0] - centre_x) - half_width, 0.0)
    beyond_y = np.maximum(np.abs(point[1] - centre_y) - _GRAPH.label_height / 2, 0.0)
    return np.hypot(beyond_x, beyond_y)


def _chip_short(gap: np.ndarray) -> np.ndarray:
    return np.maximum(_RADIUS + 4 - gap, 0.0)


def _crossings_at(
    field: _Field, mover: int, far: np.ndarray, xs: np.ndarray, ys: np.ndarray
) -> np.ndarray:
    """Count, for each spot, the edges at the mover that cross an edge sharing no end with them."""
    x, y = field.x, field.y
    apart = np.flatnonzero((field.src != mover) & (field.dst != mover))
    ax, ay = x[field.src[apart]], y[field.src[apart]]
    bx, by = x[field.dst[apart]], y[field.dst[apart]]
    tx, ty = x[far][:, None, None], y[far][:, None, None]
    px, py = xs[None, None, :], ys[None, None, :]

    # Each end of the other edge lies on opposite sides of this one, and vice versa.
    along_a = (tx - px) * (ay[None, :, None] - py) - (ty - py) * (ax[None, :, None] - px)
    along_b = (tx - px) * (by[None, :, None] - py) - (ty - py) * (bx[None, :, None] - px)
    side_p = (bx - ax)[None, :, None] * (py - ay[None, :, None]) - (by - ay)[None, :, None] * (
        px - ax[None, :, None]
    )
    side_t = (bx - ax)[None, :] * (ty[:, :, 0] - ay[None, :]) - (by - ay)[None, :] * (
        tx[:, :, 0] - ax[None, :]
    )
    shared = (field.src[apart][None, :] == far[:, None]) | (
        field.dst[apart][None, :] == far[:, None]
    )
    crossing = (along_a * along_b < 0) & (side_p * side_t[:, :, None] < 0) & ~shared[:, :, None]
    return crossing.sum(axis=(0, 1))


def _crowding(
    field: _Field, mover: int, others: np.ndarray, xs: np.ndarray, ys: np.ndarray
) -> np.ndarray:
    """Cost of the mover at each spot against the other states: spacing and lane."""
    dx = field.x[others][:, None] - xs[None, :]
    dy = field.y[others][:, None] - ys[None, :]
    apart = np.maximum(_GRAPH.node_diameter + 24 - np.hypot(dx, dy), 0.0) ** 2
    if field.well[mover]:
        lane = np.maximum(xs[None, :] - (field.x[others][:, None] - _LANE_MARGIN), 0.0)
    else:
        lane = np.maximum(field.x[others][:, None] + _LANE_MARGIN - xs[None, :], 0.0)
    near_well = field.well[others][:, None] | field.well[mover]
    lane = np.where(
        field.well[others][:, None] & field.well[mover], 0.0, lane
    )  # wells only keep left of main states
    wells = np.where(near_well, apart + 4 * lane**2, 0.0)

    level = (np.abs(dy) < _LEVEL) & ~near_well
    rank = np.where(level, np.maximum(_GRAPH.node_gap - np.abs(dx), 0.0) ** 2, 0.0)
    return (wells + rank).sum(axis=0)


def _short(distance: np.ndarray) -> np.ndarray:
    return np.maximum(CLEARANCE - distance, 0.0)


def _segment_distance(point, start, end):
    """Distance from points to segments, each an (x, y) pair that numpy broadcasts together."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    along = np.clip(
        ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
        / np.where(length == 0, 1, length),
        0.0,
        1.0,
    )
    return np.hypot(point[0] - (start[0] + along * dx), point[1] - (start[1] + along * dy))


# ======================================================================================
#                                        WELLS
# ======================================================================================


def place_wells(
    wells: list[str], positions: dict[str, tuple[float, float]], preferred: dict[str, float]
) -> None:
    """Put each well one gap left of the main flow at its neighbours' mean height."""
    left = min(x for x, _ in positions.values())
    for lane, well in enumerate(wells, start=1):
        positions[well] = (left - lane * _GRAPH.node_gap, preferred[well])


def preferred_heights(
    wells: list[str],
    edges: list[tuple[str, str]],
    positions: dict[str, tuple[float, float]],
    fallback: float,
) -> dict[str, float]:
    """Return the mean height of the placed states each well shares an edge with."""
    heights = {}
    for well in wells:
        near = [
            positions[other][1]
            for source, target in edges
            if well in (source, target)
            for other in (source, target)
            if other in positions
        ]
        heights[well] = sum(near) / len(near) if near else fallback
    return heights
