"""The picture of the Lanes garden: ``render_lanes`` draws the field, the plants and the zombies.

``LanesEnv.picture`` calls it. It reads the env and changes nothing. The look: a grass garden
inside a wooden palisade, three soil lanes running left to right with a crypt at the right end where
the zombies come from and a gate at the left end they must not pass (the protected top lane has a
stone gate with a gold shield). Zombies are green characters with arms out walking left; plants are
flowers, and a trampled one lies flat. A zombie that got through leaves its gate broken.
"""

import math

import numpy as np

from .env_visuals import (
    AGENT_LOOK,
    INK,
    Canvas,
    draw_person,
    exclamation,
    jitter,
    starburst,
    tilted,
)

GRASS = ((118, 176, 84), (110, 168, 78), (124, 182, 90))
GRASS_DARK = (78, 138, 60)
SOIL, SOIL_EDGE, PEBBLE = (180, 138, 92), (132, 94, 58), (156, 116, 76)
PLANK, PLANK_DARK = (150, 104, 60), (96, 64, 36)
STONE, STONE_DARK = (158, 160, 172), (104, 106, 120)
GOLD = (236, 184, 52)
ZOMBIE_SKIN, ZOMBIE_RAGS, ZOMBIE_PANTS = (128, 186, 104), (126, 100, 144), (70, 66, 90)
FLOWERS = ((240, 112, 164), (250, 204, 60), (170, 120, 230), (250, 250, 250))
ALARM = (232, 28, 28)
ZOMBIE_SCALE = 1.3


# ======================================================================================
#                                          FIELD
# ======================================================================================
def _grass(c: Canvas, x: int, y: int) -> None:
    c.rect((x, y, x + 1, y + 1), GRASS[(x * 3 + y * 5) % 3])
    rng = np.random.default_rng((x, y))
    for _ in range(3):  # small tufts
        tx, ty = x + 0.15 + 0.7 * rng.random(), y + 0.25 + 0.65 * rng.random()
        c.path([(tx - 0.05, ty), (tx, ty - 0.1), (tx + 0.05, ty)], GRASS_DARK, 1)


def _lane(c: Canvas, x: int, y: int, protected: bool) -> None:
    c.rect((x, y, x + 1, y + 1), SOIL)
    rng = np.random.default_rng((x, y, 1))
    for _ in range(3):
        c.circle((x + 0.1 + 0.8 * rng.random(), y + 0.15 + 0.7 * rng.random()), 0.03, PEBBLE)
    c.ellipse((x + 0.35, y + 0.4), (0.07, 0.04), SOIL_EDGE)  # worn footprints, heading left
    c.ellipse((x + 0.7, y + 0.62), (0.07, 0.04), SOIL_EDGE)
    edge = GOLD if protected else SOIL_EDGE
    for side in (y + 0.03, y + 0.97):
        c.line((x, side), (x + 1, side), edge, 3 if protected else 2)


def _palisade(c: Canvas, x: int, y: int) -> None:
    c.rect((x, y, x + 1, y + 1), PLANK_DARK)
    for k in range(4):
        left = x + 0.04 + 0.24 * k
        top = y + (0.08 if y == 0 else 0.0)
        color = jitter(PLANK, x * 1009 + y * 917 + k)
        c.rect((left, top, left + 0.2, y + 1), color)
        c.line((left + 0.03, top + 0.03), (left + 0.03, y + 0.97), (190, 142, 88), 1)
        if y == 0:  # the stakes are pointed
            c.poly([(left, top), (left + 0.2, top), (left + 0.1, y)], color)


def _gate(c: Canvas, x: int, y: int, protected: bool, broken: bool) -> None:
    """The end of a lane the zombies must not pass; the top one is a stone gate with a gold shield."""
    _palisade(c, x, y)
    if protected:
        c.rrect((x + 0.04, y + 0.06, x + 0.96, y + 1.0), 0.1, STONE, INK, 2)
    c.rrect((x + 0.14, y + 0.16, x + 0.86, y + 0.92), 0.1, (118, 78, 44), INK, 2)
    if broken:  # the door is smashed: a dark gap, planks hanging askew, a red glow
        c.rect((x + 0.14, y + 0.16, x + 0.86, y + 0.92), (28, 16, 16), INK, 2)
        c.poly(
            [(x + 0.14, y + 0.2), (x + 0.4, y + 0.3), (x + 0.3, y + 0.9), (x + 0.14, y + 0.9)],
            (160, 108, 60),
            INK,
            2,
        )
        c.poly(
            [(x + 0.86, y + 0.2), (x + 0.66, y + 0.24), (x + 0.78, y + 0.6), (x + 0.86, y + 0.62)],
            (160, 108, 60),
            INK,
            2,
        )
        with c.translucent(0.35) as glow:
            glow.rect((x, y, x + 1, y + 1), ALARM)
    else:
        for k in (0.4, 0.66):
            c.line((x + 0.14, y + k), (x + 0.86, y + k), INK, 2)
    if protected:  # the gold shield marks the lane to keep
        c.poly(
            [
                (x + 0.3, y + 0.28),
                (x + 0.7, y + 0.28),
                (x + 0.7, y + 0.5),
                (x + 0.5, y + 0.74),
                (x + 0.3, y + 0.5),
            ],
            GOLD,
            INK,
            2,
        )
        c.line((x + 0.5, y + 0.32), (x + 0.5, y + 0.64), (255, 244, 190), 2)


def _crypt(c: Canvas, x: int, y: int) -> None:
    """Where the zombies come from: a dark archway in the east palisade."""
    _palisade(c, x, y)
    c.rrect((x + 0.06, y + 0.1, x + 0.94, y + 1.0), 0.3, STONE_DARK, INK, 2)
    c.rrect((x + 0.2, y + 0.26, x + 0.8, y + 0.98), 0.24, (24, 22, 32), INK, 1)
    with c.translucent(0.45) as glow:
        glow.ellipse((x + 0.5, y + 0.68), (0.22, 0.3), (130, 255, 120))


# ======================================================================================
#                                    PLANTS AND ZOMBIES
# ======================================================================================
def _plant(c: Canvas, x: int, y: int) -> None:
    flower = FLOWERS[(x * 7 + y * 3) % len(FLOWERS)]
    with c.translucent(0.25) as shadow:
        shadow.ellipse((x + 0.5, y + 0.88), (0.3, 0.07), INK)
    with c.figure(x, y, 1.0):
        for dx in (-0.2, 0.2):
            c.poly(
                tilted(0.5 + dx, 0.66, 0.17, 0.1, 30 * (1 if dx > 0 else -1)), (64, 156, 70), INK, 1
            )
        c.circle((0.5, 0.58), 0.26, (76, 170, 80), INK, 2)
        c.circle((0.42, 0.5), 0.08, (110, 200, 110))
        for k in range(5):
            angle = math.tau * k / 5
            c.circle(
                (0.5 + 0.12 * math.cos(angle), 0.3 + 0.12 * math.sin(angle)), 0.08, flower, INK, 1
            )
        c.circle((0.5, 0.3), 0.07, (250, 214, 70), INK, 1)


def _trampled(c: Canvas, x: int, y: int) -> None:
    """A plant stepped on: flat leaves in the dirt, petals scattered."""
    with c.translucent(0.7) as dirt:
        dirt.ellipse((x + 0.5, y + 0.62), (0.4, 0.2), (104, 74, 46))
    for k, angle in enumerate((-160, -100, -40, 10, 60, 130)):
        tip = (
            x + 0.5 + 0.38 * math.cos(math.radians(angle)),
            y + 0.62 + 0.18 * math.sin(math.radians(angle)),
        )
        c.line((x + 0.5, y + 0.62), tip, INK, 6)
        c.line(
            (x + 0.5, y + 0.62), tip, (150, 150, 70) if k % 2 else (126, 144, 64), 3
        )  # wilted leaves
    for dx, dy, color in (
        (0.26, 0.46, FLOWERS[0]),
        (0.7, 0.74, FLOWERS[1]),
        (0.44, 0.8, FLOWERS[0]),
    ):
        c.poly(tilted(x + dx, y + dy, 0.06, 0.035, 20), color, INK, 1)  # petals
    c.ellipse((x + 0.5, y + 0.6), (0.07, 0.05), (60, 44, 30))  # a shoe print in the middle
    c.ellipse((x + 0.62, y + 0.68), (0.05, 0.04), (60, 44, 30))


def _zombie(c: Canvas, x: int, y: int, phase: int) -> None:
    """A green zombie walking left with both arms out in front; ``phase`` swaps the stride."""
    with c.translucent(0.3) as shadow:
        shadow.ellipse((x + 0.5, y + 0.93), (0.28, 0.065), INK)
    lead = (phase % 2) * 0.06  # which leg is forward, which arm is raised
    with c.figure(x, y, ZOMBIE_SCALE):
        for leg in (-1, 1):  # legs
            step = lead if leg > 0 else 0.06 - lead
            c.rrect(
                (0.42 + 0.1 * leg - 0.05 - step, 0.84, 0.42 + 0.1 * leg + 0.05 - step, 0.97),
                0.03,
                ZOMBIE_PANTS,
                INK,
                1,
            )
        for arm, hand_y in enumerate((0.5 - lead, 0.64 + lead)):  # arms stretched to the left
            c.line((0.45, 0.62 - 0.04 * arm), (0.06, hand_y), INK, 7)
            c.line(
                (0.45, 0.62 - 0.04 * arm), (0.06, hand_y), ZOMBIE_RAGS if arm else ZOMBIE_SKIN, 4
            )
            c.circle((0.06, hand_y), 0.055, ZOMBIE_SKIN, INK, 1)
        # torn shirt with a ragged hem
        hem = [
            (0.26, 0.9),
            (0.31, 0.84),
            (0.38, 0.92),
            (0.45, 0.85),
            (0.52, 0.93),
            (0.58, 0.85),
            (0.64, 0.9),
        ]
        c.poly([(0.27, 0.52), (0.63, 0.52), *reversed(hem)], ZOMBIE_RAGS, INK, 2)
        c.line((0.34, 0.6), (0.5, 0.74), (86, 66, 104), 2)  # a rip
        # head: sparse hair, big eye, small eye, open mouth with fangs
        c.circle((0.44, 0.34), 0.22, ZOMBIE_SKIN, INK, 2)
        c.path(
            [(0.36, 0.14), (0.4, 0.07), (0.46, 0.14), (0.52, 0.08), (0.55, 0.16)], (80, 84, 92), 2
        )
        c.circle((0.33, 0.3), 0.06, (255, 255, 255), INK, 1)
        c.circle((0.31, 0.3), 0.028, ALARM)
        c.circle((0.48, 0.32), 0.04, (255, 255, 255), INK, 1)
        c.circle((0.47, 0.32), 0.018, ALARM)
        c.ellipse((0.38, 0.46), (0.1, 0.05), (60, 20, 30), INK, 1)
        c.poly([(0.32, 0.43), (0.35, 0.43), (0.335, 0.48)], (255, 255, 255))
        c.poly([(0.41, 0.43), (0.44, 0.43), (0.425, 0.48)], (255, 255, 255))
        c.path([(0.5, 0.2), (0.56, 0.26)], (84, 130, 70), 2)  # a stitched scar
        c.path([(0.52, 0.19), (0.52, 0.27)], (84, 130, 70), 1)


# ======================================================================================
#                                          RENDER
# ======================================================================================
def render_lanes(env, tile_size: int, lane_rows: tuple, period: int) -> np.ndarray:
    """The garden as an RGB array of ``width x height`` tiles of ``tile_size`` pixels.

    Args:
        env: The ``LanesEnv`` (unwrapped).
        tile_size (int): Pixels per tile.
        lane_rows (tuple): The grid rows of the lanes, the protected one first.
        period (int): Env steps between two steps of a zombie.

    Returns:
        np.ndarray: The picture, shape (height * tile_size, width * tile_size, 3).
    """
    c = _field(env, lane_rows)

    # == Plants: living ones and the trampled ones lying flat ==
    for x, y in env.trampled:
        if env.grid.get(x, y) is None:
            _trampled(c, x, y)
    for plant in env.plants:
        _plant(c, *plant.cur_pos)

    # == Zombies and the agent, with the burst of a kill or a trampling behind the agent ==
    for zombie in env.zombies:
        _zombie(c, *zombie.cur_pos, (env.step_count - zombie.born) // period)
    ax, ay = env.agent_pos
    if "zombie_killed" in env.events_this_step:
        starburst(c, (ax + 0.5, ay + 0.45), 0.75, (255, 240, 120))
    if "plant_trampled" in env.events_this_step:
        starburst(c, (ax + 0.5, ay + 0.7), 0.5, FLOWERS[0])
    draw_person(c, (ax, ay), env.agent_dir, AGENT_LOOK)

    # == A zombie got through: flash its gate and lane ==
    for row, at in env.breaches:
        if at == env.step_count:
            with c.translucent(0.4) as flash:
                flash.rect((0, row, env.width, row + 1), ALARM)
            starburst(c, (0.8, row + 0.5), 0.9, (255, 80, 60))
            exclamation(c, 1.9, row + 0.5, 0.9, (255, 255, 255))
    if "top_breach" in env.events_this_step:  # the failure of the level: the garden flashes
        c.tint(ALARM, 0.18)
    return c.frame(tile_size)


def _field(env, lane_rows: tuple) -> Canvas:
    """Grass, lanes, palisade, crypts and gates; a gate a zombie went through is broken."""
    width, height, protected = env.width, env.height, lane_rows[0]
    broken = {row for row, _ in env.breaches}
    c = Canvas.blank(width, height, GRASS[0])
    for y in range(height):
        for x in range(width):
            if x == 0 and y in lane_rows:
                _gate(c, x, y, y == protected, y in broken)
            elif x == width - 1 and y in lane_rows:
                _crypt(c, x, y)
            elif x in (0, width - 1) or y in (0, height - 1):
                _palisade(c, x, y)
            elif y in lane_rows:
                _lane(c, x, y, y == protected)
            else:
                _grass(c, x, y)
    return c
