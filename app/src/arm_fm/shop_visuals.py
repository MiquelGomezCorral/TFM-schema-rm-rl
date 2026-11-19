"""The picture of the shop: ``render_shop`` draws the room, the people and the food from the env.

``ShopEnv.picture`` calls it. It reads the env and changes nothing. The look: a wooden floor with
brick walls, the counter with the client at it, the pantry shelf, the stove (a pot on Shop-Pot that
boils over), the siren switch and lamp. While the siren rings the whole room gets a red tint, turning
red rays from the lamp and a flashing border, so it is seen from everywhere.
"""

import math
from functools import cache

import numpy as np

from .env_visuals import (
    AGENT_LOOK,
    CLIENT_HAPPY,
    CLIENT_LOOK,
    INK,
    Canvas,
    draw_food,
    draw_person,
    exclamation,
    food_in_hands,
    heart,
    jitter,
    starburst,
    tilted,
)

FLOOR = ((226, 190, 140), (219, 182, 131), (232, 197, 148))
SEAM = (184, 144, 98)
BRICK, MORTAR = (150, 104, 92), (102, 74, 68)
WOOD, WOOD_DARK, WOOD_LIGHT = (204, 148, 80), (128, 84, 42), (232, 186, 118)
STEEL, IRON = (190, 196, 206), (58, 58, 66)
ALARM = (232, 28, 28)
BUBBLE = (255, 255, 255)


# ======================================================================================
#                                       STATIC ROOM
# ======================================================================================
def _brick(c: Canvas, x: int, y: int) -> None:
    c.rect((x, y, x + 1, y + 1), MORTAR)
    for course in range(4):
        offset = 0.25 * ((course + x + y) % 2)
        for k in range(-1, 3):
            left, right = x + offset + 0.5 * k, x + offset + 0.5 * (k + 1)
            left, right = max(left, x), min(right, x + 1)
            if right - left > 0.06:
                top = y + 0.25 * course
                color = jitter(BRICK, x * 1009 + y * 917 + course * 31 + k)
                c.rect((left + 0.02, top + 0.03, right - 0.02, top + 0.22), color)
                c.line((left + 0.03, top + 0.04), (right - 0.03, top + 0.04), WOOD_LIGHT, 1)


def _floor(c: Canvas, x: int, y: int, size: int) -> None:
    for half in range(2):
        top = y + 0.5 * half
        c.rect((x, top, x + 1, top + 0.5), FLOOR[(x * 3 + y * 5 + half) % 3])
        c.line((x, top), (x + 1, top), SEAM, 1)
        seam = x + (0.3 if (x + y + half) % 2 else 0.75)
        c.line((seam, top), (seam, top + 0.5), SEAM, 1)
    with c.translucent(0.22) as shade:  # the walls throw a soft shadow on the floor next to them
        last = size - 2
        if y == 1:
            shade.rect((x, y, x + 1, y + 0.14), INK)
        if x == 1:
            shade.rect((x, y, x + 0.14, y + 1), INK)
        if x == last:
            shade.rect((x + 0.86, y, x + 1, y + 1), INK)


def _wood_block(c: Canvas, cells: set, facing: int) -> None:
    """Counter or shelf units in a column: ``facing`` is the side (1 or -1 in x) that faces the room."""
    for x, y in cells:
        c.rect((x, y, x + 1, y + 1), WOOD)
        for k in (0.33, 0.66):
            c.line((x + 0.04, y + k), (x + 0.96, y + k), WOOD_LIGHT, 1)
        front = (x + 0.8, x + 1) if facing > 0 else (x, x + 0.2)
        c.rect((front[0], y, front[1], y + 1), WOOD_DARK)
        if (x, y - 1) not in cells:
            c.line((x, y), (x + 1, y), INK, 2)
        if (x, y + 1) not in cells:
            c.line((x, y + 1), (x + 1, y + 1), INK, 2)
        edge = x + 1 if facing > 0 else x
        c.line((edge, y), (edge, y + 1), INK, 2)


def _register(c: Canvas, x: int, y: int) -> None:
    c.rrect((x + 0.2, y + 0.25, x + 0.75, y + 0.75), 0.05, STEEL, INK, 1)
    c.rect((x + 0.27, y + 0.31, x + 0.5, y + 0.45), (120, 214, 150), INK, 1)
    for k in range(3):
        c.circle((x + 0.3 + 0.12 * k, y + 0.6), 0.035, INK)


def _shelf_goods(c: Canvas, cells: list) -> None:
    """Jars on the end units of the pantry shelf; the middle unit holds the portion."""
    top, bottom = min(cells, key=lambda cell: cell[1]), max(cells, key=lambda cell: cell[1])
    for (x, y), colors in (
        (top, ((196, 70, 70), (88, 150, 210), (120, 180, 90))),
        (bottom, ((236, 170, 60), (150, 100, 190))),
    ):
        for k, color in enumerate(colors):
            jx, jy = x + 0.3 + 0.2 * (k % 2), y + 0.28 + 0.26 * (k // 2) + 0.0
            c.circle((jx, jy), 0.12, color, INK, 1)
            c.circle((jx - 0.04, jy - 0.04), 0.035, (255, 255, 255))


def _door(c: Canvas, x: int, y: int) -> None:
    """The shop door in the west wall behind the counter, where the clients come in."""
    _brick(c, x, y)
    c.rrect((x + 0.14, y + 0.08, x + 0.86, y + 0.92), 0.06, (112, 72, 44), INK, 2)
    c.rrect((x + 0.26, y + 0.2, x + 0.74, y + 0.56), 0.04, (170, 214, 236), INK, 1)
    c.circle((x + 0.7, y + 0.72), 0.045, (240, 196, 70), INK, 1)


@cache
def _room(layout) -> np.ndarray:
    """The parts that never change: floor, walls, door, counter, shelf and their goods."""
    n = layout.size
    c = Canvas.blank(n, n, MORTAR)
    for y in range(n):
        for x in range(n):
            if 0 < x < n - 1 and 0 < y < n - 1:
                _floor(c, x, y, n)
            else:
                _brick(c, x, y)
    client_x, client_y = layout.client
    _door(c, 0, client_y)
    counter = {layout.client, *(cell for cell in layout.counter if cell[0] == client_x)}
    shelf = {layout.pantry, *(cell for cell in layout.counter if cell[0] == layout.pantry[0])}
    _wood_block(c, counter, 1)
    _wood_block(c, shelf, -1)
    _register(c, *min(counter, key=lambda cell: cell[1]))
    _shelf_goods(c, sorted(shelf))
    return c.img


# ======================================================================================
#                                    STOVE, SWITCH, LAMP
# ======================================================================================
def _stove(c: Canvas, layout, pot: bool, boiling: bool, prepared_now: bool) -> None:
    x, y = layout.stove
    c.rect((x, y, x + 1, y + 1), STEEL, INK, 2)  # the cooker: steel with a black hob
    c.rrect((x + 0.07, y + 0.07, x + 0.93, y + 0.74), 0.06, (36, 36, 42), INK, 1)
    for k in range(3):
        c.circle((x + 0.25 + 0.25 * k, y + 0.88), 0.06, (90, 96, 108), INK, 1)
    flame = (255, 110, 40) if boiling else (120, 124, 136)
    c.circle((x + 0.5, y + 0.4), 0.36, (24, 24, 28), flame, 3)
    if boiling:
        with c.translucent(0.2) as glow:
            for radius in (1.1, 0.8, 0.55):
                glow.circle((x + 0.5, y + 0.45), radius, (255, 70, 30))
    if pot:
        _pot(c, x, y, boiling)
    else:  # a pan with a wooden handle
        c.circle((x + 0.5, y + 0.4), 0.3, (84, 86, 96), INK, 2)
        c.circle((x + 0.5, y + 0.4), 0.23, (52, 54, 62))
        c.rrect((x + 0.78, y + 0.35, x + 1.1, y + 0.46), 0.04, (150, 100, 56), INK, 1)
    if prepared_now:  # the food just came off the stove cooked
        starburst(c, (x + 0.5, y + 0.4), 0.4, (255, 220, 70))


def _pot(c: Canvas, x: int, y: int, boiling: bool) -> None:
    cx, cy = x + 0.5, y + 0.4
    for side in (-1, 1):
        c.rrect(
            (cx + side * 0.38 - 0.07, cy - 0.05, cx + side * 0.38 + 0.07, cy + 0.05),
            0.03,
            STEEL,
            INK,
            1,
        )
    c.circle((cx, cy), 0.31, (62, 112, 188), INK, 2)  # a blue enamel pot
    if not boiling:
        c.circle((cx, cy), 0.25, (96, 148, 222), INK, 1)  # the lid
        c.circle((cx, cy), 0.06, STEEL, INK, 1)
        return
    foam, foam_edge = (252, 246, 236), (206, 194, 184)
    rng = np.random.default_rng(7)  # a fixed froth: the same state is always the same picture
    for dx, top, bottom in ((-0.2, 0.55, 1.0), (0.04, 0.6, 1.14), (0.22, 0.55, 0.95)):
        c.rrect(
            (x + 0.5 + dx - 0.07, y + top, x + 0.5 + dx + 0.07, y + bottom),
            0.07,
            foam,
            foam_edge,
            1,
        )
    c.ellipse((x + 0.5, y + 1.12), (0.42, 0.12), foam, foam_edge, 1)  # it spills onto the floor
    for k in range(12):  # the froth over the rim
        angle = math.tau * k / 12
        c.circle(
            (cx + 0.28 * math.cos(angle), cy + 0.28 * math.sin(angle)),
            0.08 + 0.03 * rng.random(),
            foam,
            foam_edge,
            1,
        )
    c.circle((cx, cy), 0.22, (40, 70, 128))  # the boiling water, covered by bubbles
    for _ in range(9):
        c.circle(
            (cx - 0.17 + 0.34 * rng.random(), cy - 0.17 + 0.34 * rng.random()),
            0.06 + 0.03 * rng.random(),
            foam,
            foam_edge,
            1,
        )
    c.poly(
        tilted(cx + 0.34, cy - 0.18, 0.2, 0.07, -38), (96, 148, 222), INK, 1
    )  # the lid, pushed aside (it must stay in the tile: row 0 is the top edge of the picture)


def _steam(c: Canvas, layout) -> None:
    """Steam puffs beside the stove's front cell, so the agent standing there stays visible."""
    x, y = layout.stove
    with c.translucent(0.55) as steam:
        for dx, dy, radius in (
            (-0.45, 1.3, 0.2),
            (1.4, 1.35, 0.22),
            (-0.55, 1.95, 0.26),
            (1.5, 2.0, 0.28),
        ):
            steam.circle((x + dx, y + dy), radius, (248, 248, 252))


def _switch(c: Canvas, layout, ringing: bool) -> None:
    x, y = layout.switch
    c.rrect((x + 0.14, y + 0.1, x + 0.86, y + 0.9), 0.08, STEEL, INK, 2)
    c.rrect((x + 0.43, y + 0.26, x + 0.57, y + 0.78), 0.07, (60, 60, 70))
    knob_y, color = (y + 0.34, (240, 50, 50)) if ringing else (y + 0.7, (70, 190, 110))
    c.circle((x + 0.5, knob_y), 0.12, color, INK, 2)
    c.circle((x + 0.28, y + 0.24), 0.06, color, INK, 1)


def _lamp(c: Canvas, layout, ringing: bool) -> None:
    x, y = layout.size - 3, 0
    c.rrect((x + 0.2, y + 0.62, x + 0.8, y + 0.9), 0.05, IRON, INK, 1)
    if ringing:
        with c.translucent(0.45) as glow:
            glow.circle((x + 0.5, y + 0.5), 0.62, (255, 210, 80))
    c.circle((x + 0.5, y + 0.48), 0.28, ALARM if ringing else (128, 54, 54), INK, 2)
    c.circle((x + 0.42, y + 0.4), 0.07, (255, 255, 255) if ringing else (170, 120, 120))


def _alarm(c: Canvas, layout, step: int) -> None:
    """The siren: red tint, rays turning out of the lamp over the whole room, a flashing border."""
    n = layout.size
    lamp = (n - 2.5, 0.48)
    c.tint(ALARM, 0.12)
    with c.translucent(0.2) as rays:
        for k in range(12):
            turn = math.radians(30 * k + 14 * step)
            wedge = [lamp] + [
                (lamp[0] + 2 * n * math.cos(turn + w), lamp[1] + 2 * n * math.sin(turn + w))
                for w in (-0.12, 0.12)
            ]
            rays.poly(wedge, ALARM)
    for k in range(8):  # short strokes round the lamp itself
        angle = math.tau * k / 8 + 0.2 * step
        c.line(
            (lamp[0] + 0.4 * math.cos(angle), lamp[1] + 0.4 * math.sin(angle)),
            (lamp[0] + 0.62 * math.cos(angle), lamp[1] + 0.62 * math.sin(angle)),
            (255, 214, 64),
            3,
        )
    with c.translucent(0.9 if step % 2 else 0.5) as border:
        border.rect((0.04, 0.04, n - 0.04, n - 0.04), edge=ALARM, width=9)


# ======================================================================================
#                                     FOOD AND CLIENT
# ======================================================================================
def _fallen_food(c: Canvas, x: int, y: int, prepared: bool, just_fell: bool) -> None:
    """A portion slipped off its plate: a stain, a tilted plate, crumbs and food beside it."""
    food = (176, 104, 52) if prepared else (252, 232, 150)
    with c.figure(x, y, 1.25):
        with c.translucent(0.35) as stain:
            stain.ellipse((0.52, 0.72), (0.4, 0.2), (140, 98, 52))
        c.poly(tilted(0.4, 0.6, 0.3, 0.2, -22), (250, 250, 244), INK, 1)  # the plate, tilted
        c.poly(tilted(0.4, 0.6, 0.19, 0.12, -22), (222, 226, 224), None, 1)
        c.poly(tilted(0.68, 0.76, 0.18, 0.12, 15), food, INK, 1)  # the food beside it
        for dx, dy in ((0.2, 0.84), (0.5, 0.9), (0.86, 0.6), (0.8, 0.9), (0.26, 0.36)):
            c.circle((dx, dy), 0.035, food, INK, 1)
        if just_fell:  # the impact: strokes round the spot
            for k in range(5):
                angle = math.radians(200 + 35 * k)
                near = (0.5 + 0.4 * math.cos(angle), 0.6 + 0.4 * math.sin(angle))
                far = (0.5 + 0.56 * math.cos(angle), 0.6 + 0.56 * math.sin(angle))
                c.line(near, far, (236, 150, 30), 3)


def _client(c: Canvas, layout, order_taken: bool, served: bool) -> None:
    x, y = layout.client
    draw_person(c, (x, y), 0, CLIENT_HAPPY if served else CLIENT_LOOK)
    bx, by = x + 0.55, y - 1.0  # the bubble sits above and beside, off the agent's cell
    c.poly([(bx + 0.15, by + 0.62), (bx + 0.45, by + 0.62), (x + 0.62, y - 0.06)], BUBBLE, INK, 2)
    c.rrect((bx, by, bx + 0.95, by + 0.68), 0.16, BUBBLE, INK, 2)
    c.rect((bx + 0.14, by + 0.6, bx + 0.46, by + 0.64), BUBBLE)
    if served:
        heart(c, bx + 0.475, by + 0.34, 0.42, (230, 50, 80))
    elif order_taken:
        draw_food(c, bx + 0.475, by + 0.34, 0.25, True)
    else:
        exclamation(c, bx + 0.475, by + 0.34, 0.52, (240, 140, 20))


# ======================================================================================
#                                          RENDER
# ======================================================================================
def render_shop(env, tile_size: int, prepared_color: str) -> np.ndarray:
    """The shop as an RGB array of ``size x size`` tiles of ``tile_size`` pixels.

    Args:
        env: The ``ShopEnv`` (unwrapped).
        tile_size (int): Pixels per tile.
        prepared_color (str): The colour that marks prepared food on the env's food objects.

    Returns:
        np.ndarray: The picture, shape (size * tile_size, size * tile_size, 3).
    """
    layout, events = env.layout, env.events_this_step
    c = Canvas(_room(layout).copy())
    _stove(c, layout, env.pot, env.pot_boiling, "prepare" in events)
    _switch(c, layout, env.siren_ringing)
    _lamp(c, layout, env.siren_ringing)

    # == Food: the portion on the shelf, and any lying on the floor ==
    for x in range(layout.size):
        for y in range(layout.size):
            item = env.grid.get(x, y)
            if item is None or item.type != "box":
                continue
            prepared = item.color == prepared_color
            if (x, y) == layout.pantry:
                draw_food(c, x + 0.5, y + 0.5, 0.3, prepared)
            else:
                _fallen_food(c, x, y, prepared, "fall" in events)

    # == People ==
    served = "serve" in events  # the client is already gone from the grid: show it leaving happy
    if env.client_present or served:
        _client(c, layout, env.order_taken, served)
    held = env.carrying
    hands = None if held is None else food_in_hands(held.color == prepared_color)
    draw_person(c, tuple(env.agent_pos), env.agent_dir, AGENT_LOOK, hands)

    if env.pot_boiling:
        _steam(c, layout)
    if env.siren_ringing:
        _alarm(c, layout, env.step_count)
    return c.frame(tile_size)
