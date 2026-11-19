"""Drawing helpers for the level renderers: a canvas in tile units and the shared characters.

``shop_visuals`` and ``lanes_visuals`` draw a level's picture with them. Everything is drawn at
``TILE`` pixels per tile with anti-aliasing, then ``Canvas.frame`` scales it to the caller's tile
size. Drawing only reads the env, so observations, rewards and labels never go through here.
"""

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import NamedTuple

import cv2
import numpy as np

from .service_room import DIRECTIONS

TILE = 64  # pixels per tile while drawing
_SHIFT = 4  # OpenCV fixed-point bits: shapes sit on sub-pixel positions
AA = cv2.LINE_AA
INK = (46, 36, 42)  # the outline of every character and object

Color = tuple[int, int, int]
Point = tuple[float, float]
Box = tuple[float, float, float, float]  # left, top, right, bottom
Held = Callable[["Canvas", float, float, float], None]  # draws the held item: canvas, x, y, radius


# ======================================================================================
#                                         CANVAS
# ======================================================================================
class Canvas:
    """An RGB picture of tiles; every position and size is in tile units (1.0 = one tile)."""

    def __init__(self, img: np.ndarray) -> None:
        self.img = img
        self._scale, self._origin = 1.0, (0.0, 0.0)  # see ``figure``

    @classmethod
    def blank(cls, cols: int, rows: int, base: Color) -> "Canvas":
        img = np.empty((rows * TILE, cols * TILE, 3), np.uint8)
        img[:] = base
        return cls(img)

    @contextmanager
    def figure(self, x: float, y: float, scale: float) -> Iterator[None]:
        """Draw in the local units of a figure standing in tile (x, y), scaled up around its feet.

        Inside the block (0, 0) is the tile's top-left corner and (1, 1) its bottom-right, but
        everything is ``scale`` times bigger and rises above the tile (and spills over its sides).
        """
        saved = self._scale, self._origin
        self._scale, self._origin = scale, (x + 0.5 - 0.5 * scale, y + 1 - scale)
        yield
        self._scale, self._origin = saved

    def _fixed(self, value: float) -> int:
        return round(value * TILE * (1 << _SHIFT))

    def _length(self, value: float) -> int:
        return self._fixed(value * self._scale)

    def _point(self, x: float, y: float) -> tuple[int, int]:
        ox, oy = self._origin
        return self._fixed(ox + x * self._scale), self._fixed(oy + y * self._scale)

    def _width(self, width: int) -> int:
        return max(1, round(width * self._scale))

    def poly(self, points, fill=None, edge=None, width=2, closed=True) -> None:
        pts = np.array([self._point(x, y) for x, y in points], np.int32)
        if fill is not None:
            cv2.fillPoly(self.img, [pts], fill, AA, _SHIFT)
        if edge is not None:
            cv2.polylines(self.img, [pts], closed, edge, self._width(width), AA, _SHIFT)

    def rect(self, box: Box, fill=None, edge=None, width=2) -> None:
        x0, y0, x1, y1 = box
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, edge, width)

    def rrect(self, box: Box, radius: float, fill=None, edge=None, width=2) -> None:
        """A rectangle with rounded corners."""
        x0, y0, x1, y1 = box
        corners = ((x1 - radius, y0 + radius, -90), (x1 - radius, y1 - radius, 0))
        corners += ((x0 + radius, y1 - radius, 90), (x0 + radius, y0 + radius, 180))
        points = []
        for cx, cy, start in corners:
            for k in range(5):
                angle = math.radians(start + 90 * k / 4)
                points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        self.poly(points, fill, edge, width)

    def ellipse(self, center: Point, radii: Point, fill=None, edge=None, width=2) -> None:
        middle, axes = self._point(*center), (self._length(radii[0]), self._length(radii[1]))
        if fill is not None:
            cv2.ellipse(self.img, middle, axes, 0, 0, 360, fill, -1, AA, _SHIFT)
        if edge is not None:
            cv2.ellipse(self.img, middle, axes, 0, 0, 360, edge, self._width(width), AA, _SHIFT)

    def circle(self, center: Point, radius: float, fill=None, edge=None, width=2) -> None:
        self.ellipse(center, (radius, radius), fill, edge, width)

    def line(self, start: Point, end: Point, color: Color, width=2) -> None:
        cv2.line(
            self.img,
            self._point(*start),
            self._point(*end),
            color,
            self._width(width),
            AA,
            _SHIFT,
        )

    def path(self, points: list[Point], color: Color, width=2) -> None:
        """An open line through the points."""
        self.poly(points, None, color, width, closed=False)

    @contextmanager
    def translucent(self, alpha: float) -> Iterator["Canvas"]:
        """Draw on a copy of the picture that is mixed in at ``alpha`` when the block ends."""
        layer = Canvas(self.img.copy())
        layer._scale, layer._origin = (
            self._scale,
            self._origin,
        )  # the layer draws where the block does
        yield layer
        self.img = cv2.addWeighted(self.img, 1 - alpha, layer.img, alpha, 0)

    def tint(self, color: Color, alpha: float) -> None:
        """Mix a colour over the whole picture."""
        self.img = cv2.addWeighted(self.img, 1 - alpha, np.full_like(self.img, color), alpha, 0)

    def frame(self, tile_size: int) -> np.ndarray:
        """The picture at ``tile_size`` pixels per tile."""
        if tile_size == TILE:
            return self.img
        height, width = self.img.shape[:2]
        size = (width * tile_size // TILE, height * tile_size // TILE)
        return cv2.resize(self.img, size, interpolation=cv2.INTER_AREA)


def tilted(cx: float, cy: float, rx: float, ry: float, degrees: float) -> list[Point]:
    """The outline of an ellipse turned by ``degrees``, for ``Canvas.poly``."""
    turn = math.radians(degrees)
    points = []
    for k in range(24):
        angle = math.tau * k / 24
        px, py = rx * math.cos(angle), ry * math.sin(angle)
        points.append(
            (
                cx + px * math.cos(turn) - py * math.sin(turn),
                cy + px * math.sin(turn) + py * math.cos(turn),
            )
        )
    return points


def jitter(color: Color, seed: int, spread: int = 8) -> Color:
    """The colour nudged by a fixed amount drawn from ``seed``: the same tile always looks the same."""
    shift = np.random.default_rng(seed).integers(-spread, spread + 1)
    return tuple(int(np.clip(channel + shift, 0, 255)) for channel in color)


def starburst(c: Canvas, center: Point, radius: float, fill: Color, points: int = 8) -> None:
    """A spiky flash: the mark of an impact."""
    cx, cy = center
    shape = []
    for k in range(points * 2):
        angle = math.pi * k / points
        reach = radius if k % 2 == 0 else radius * 0.5
        shape.append((cx + reach * math.cos(angle), cy + reach * math.sin(angle)))
    c.poly(shape, fill, INK, 1)


def heart(c: Canvas, cx: float, cy: float, size: float, fill: Color) -> None:
    c.circle((cx - size * 0.25, cy - size * 0.15), size * 0.28, fill)
    c.circle((cx + size * 0.25, cy - size * 0.15), size * 0.28, fill)
    c.poly(
        [
            (cx - size * 0.5, cy - size * 0.05),
            (cx + size * 0.5, cy - size * 0.05),
            (cx, cy + size * 0.5),
        ],
        fill,
    )


def exclamation(c: Canvas, cx: float, cy: float, size: float, color: Color) -> None:
    c.rrect(
        (cx - size * 0.1, cy - size * 0.5, cx + size * 0.1, cy + size * 0.12), size * 0.08, color
    )
    c.circle((cx, cy + size * 0.36), size * 0.11, color)


# ======================================================================================
#                                          FOOD
# ======================================================================================
def draw_food(c: Canvas, cx: float, cy: float, radius: float, prepared: bool) -> None:
    """One portion on a plate: a pale raw lump, or a cooked patty with grill marks and a leaf."""
    c.circle((cx, cy), radius, (250, 250, 244), INK, 1)
    c.circle((cx, cy), radius * 0.72, (222, 226, 224))
    if prepared:
        c.ellipse((cx, cy), (radius * 0.58, radius * 0.46), (176, 104, 52), (104, 56, 26), 1)
        for k in (-1, 0, 1):
            x = cx + k * radius * 0.26
            c.line(
                (x - radius * 0.1, cy - radius * 0.3),
                (x + radius * 0.1, cy + radius * 0.3),
                (96, 50, 24),
                1,
            )
        c.poly(
            tilted(cx - radius * 0.36, cy - radius * 0.34, radius * 0.3, radius * 0.18, -35),
            (96, 178, 72),
            (46, 108, 40),
            1,
        )
    else:
        c.ellipse((cx, cy), (radius * 0.56, radius * 0.46), (252, 232, 150), (196, 164, 72), 1)
        for dx, dy in ((-0.22, -0.12), (0.08, -0.2), (0.26, 0.06), (-0.06, 0.16)):
            c.circle((cx + dx * radius, cy + dy * radius), radius * 0.07, (206, 166, 74))


def food_in_hands(prepared: bool) -> Held:
    return lambda c, x, y, radius: draw_food(c, x, y, radius, prepared)


# ======================================================================================
#                                       CHARACTERS
# ======================================================================================
class Look(NamedTuple):
    skin: Color
    hair: Color
    shirt: Color
    happy: bool = False


AGENT_LOOK = Look((247, 208, 170), (74, 48, 36), (34, 140, 196))  # brown hair, blue shirt
CLIENT_LOOK = Look((236, 184, 146), (244, 196, 64), (230, 104, 58))  # blond hair, orange shirt
CLIENT_HAPPY = CLIENT_LOOK._replace(happy=True)  # a served client: open smile, rosy cheeks

PERSON_SCALE = 1.3  # a person is a bit taller than its tile, so its face and hands read

# Per facing (right, down, left, up): where the held item and the hands go, in figure units.
_HELD_AT = ((0.84, 0.64, 0.15), (0.5, 0.80, 0.17), (0.16, 0.64, 0.15), (0.5, 0.13, 0.14))
_HANDS_FULL = (
    ((0.70, 0.62),),
    ((0.30, 0.74), (0.70, 0.74)),
    ((0.30, 0.62),),
    ((0.27, 0.27), (0.73, 0.27)),
)
_HANDS_FREE = (
    ((0.68, 0.70),),
    ((0.26, 0.74), (0.74, 0.74)),
    ((0.32, 0.70),),
    ((0.28, 0.66), (0.72, 0.66)),
)


def draw_person(
    c: Canvas, tile: Point, direction: int, look: Look, held: Held | None = None
) -> None:
    """A person standing in ``tile``: a round head with hair and eyes looking the way it faces.

    A body is below the head and ``held`` is drawn in the hands.
    """
    with c.figure(*tile, PERSON_SCALE):
        _person(c, direction, look, held)


def _person(c: Canvas, direction: int, look: Look, held: Held | None) -> None:
    dx, dy = DIRECTIONS[direction]
    sideways = dx != 0
    with c.translucent(0.3) as shadow:
        shadow.ellipse((0.5, 0.93), (0.28, 0.065), INK)

    # == Body and arms ==
    bx, half = 0.5 - 0.05 * dx, 0.17 if sideways else 0.23
    c.rrect((bx - half, 0.52, bx + half, 0.92), 0.12, look.shirt, INK)
    hands = (_HANDS_FULL if held else _HANDS_FREE)[direction]
    shoulders = [(bx, 0.6)] if sideways else [(bx - half * 0.8, 0.6), (bx + half * 0.8, 0.6)]
    for shoulder, hand in zip(shoulders, hands, strict=True):
        c.line(shoulder, hand, INK, 7)
        c.line(shoulder, hand, look.shirt, 4)
    for hand in hands:
        c.circle(hand, 0.06, look.skin, INK, 1)

    # == Head: hair all round, the face turned toward the facing ==
    hx, hy, radius = bx + 0.05 * dx, 0.36 + 0.02 * (dy > 0), 0.21
    c.circle((hx, hy), radius, look.hair, INK)
    c.circle((hx - 0.07, hy - radius + 0.02), 0.07, look.hair, INK, 1)
    c.circle((hx + 0.06, hy - radius), 0.06, look.hair, INK, 1)
    c.circle((hx, hy), radius - 0.02, look.hair)  # hides the tufts' inner outline
    if direction != 3:  # facing up shows the back of the head: no face
        _face(c, (hx + 0.06 * dx, hy + (0.05 if dy > 0 else 0.03)), direction, look)

    if held:
        held(c, *_HELD_AT[direction])


def _face(c: Canvas, center: Point, direction: int, look: Look) -> None:
    fx, fy = center
    dx, _ = DIRECTIONS[direction]
    c.circle((fx, fy), 0.17, look.skin, INK, 1)
    eyes = [(fx - 0.07, fy - 0.01), (fx + 0.07, fy - 0.01)]
    if dx:
        eyes = [(fx + dx * 0.03, fy - 0.01), (fx + dx * 0.11, fy - 0.01)]
    for ex, ey in eyes:
        c.circle((ex, ey), 0.045, (255, 255, 255), INK, 1)
        pupil = (dx * 0.015, 0.012 if direction == 1 else 0)
        c.circle((ex + pupil[0], ey + pupil[1]), 0.026, INK)
    mouth_x = fx + dx * 0.09
    if look.happy:
        c.ellipse((mouth_x, fy + 0.08), (0.06, 0.045), (196, 58, 58), INK, 1)
        for ex, _ in eyes:
            with c.translucent(0.5) as blush:
                blush.circle((ex, fy + 0.06), 0.04, (240, 90, 120))
    else:
        c.path(
            [(mouth_x - 0.045, fy + 0.085), (mouth_x, fy + 0.105), (mouth_x + 0.045, fy + 0.085)],
            INK,
            2,
        )
