"""TeX of figure 5: the six simplified machines of the example cards, FARM beside ARM-FM.

One arrow per pair of states (``records.merged_arrows``), labelled with its reward, or ``mixed`` when its
transitions pay differently, and with the number of transitions when it holds more than one. No
propositions. The arrow colour follows the reward sign as in ``render-rm`` (``_edge_class`` in
``app/src/utils/visualization.py``): green when it pays, red when it only costs, grey when it pays nothing
or holds both signs. Node styles are the thesis's (``farm graph``): double ring = final, grey = the well.
The positions are laid out by hand, in cm, so every drawing fits half a text width.
"""

COLUMN = {"farm": 0.0, "arm-fm": 6.6}  # x of each column's origin, cm
LEFT, RIGHT = (
    -0.95,
    13.75,
)  # the initial arrow reaches LEFT; every state stays left of RIGHT, so the picture is 15 cm
ROW_GAP = 0.9  # between a drawing row and the next card's title
TITLE_GAP = 0.55
# {(card, arm): (positions, {"src>dst": (to-options, label-options)})}; default arrow: straight, label above
LAYOUT = {
    ("DoorKey", "farm"): (
        {"u0": (0, 0), "u1": (1.6, 0), "u3": (3.2, 0), "u4": (4.8, 0), "u2": (2.4, -2.0)},
        {
            "u0>u3": ("bend left=38", "above"),
            "u1>u4": ("bend left=38", "above"),
            "u0>u4": ("bend left=55", "above"),
            "u0>u2": ("", "below left, pos=0.45"),
            "u1>u2": ("", "right, xshift=2pt, pos=0.5"),
        },
    ),
    ("DoorKey", "arm-fm"): (
        {"u0": (0, 0), "u1": (1.7, 0), "u2": (3.4, 0), "u3": (5.1, 0)},
        {},
    ),
    ("Blocked box", "farm"): (
        {"u0": (0, 0), "u1": (3.2, 0)},
        {"u0>u0": ("loop above", "above")},
    ),
    ("Blocked box", "arm-fm"): (
        {"u0": (0, 0), "u1": (1.7, 0), "u2": (3.4, 0), "u3": (5.1, 0), "uF": (6.8, 0)},
        {
            "u0>u0": ("loop above", "above"),
            "u1>u2": ("bend left=22", "above"),
            "u2>u1": ("bend left=22", "below"),
        },
    ),
    ("Box carry", "farm"): (
        {"u0": (0, 0), "u1": (0, -2.6), "u2": (2.6, 1.3), "u4": (2.6, -1.3), "u3": (5.2, 0)},
        {
            "u0>u1": ("bend left=20", "right"),
            "u1>u0": ("bend left=20", "left"),
            "u0>u2": ("", "above left, pos=0.55"),
            "u0>u4": ("", "below left, pos=0.55"),
            "u0>u3": ("", "pos=0.3"),  # on the line, clear of the two arrows leaving u0 beside it
            "u1>u4": ("", "below right, pos=0.5"),
            "u1>u3": ("bend right=25", "below, pos=0.55"),
            "u2>u3": ("", "above right, pos=0.5"),
            "u2>u4": ("", "right, pos=0.25"),
            "u4>u3": ("", "above left, pos=0.5"),  # clear of the curve u1>u3 that ends at u3
        },
    ),
    ("Box carry", "arm-fm"): (
        {"u0": (0, 0), "u1": (2.6, -1.7), "uF": (5.2, 0)},
        {
            "u0>u1": ("bend left=18", "above right, pos=0.5"),
            "u1>u0": ("bend left=18", "below left, pos=0.5"),
        },
    ),
}
CARDS = ("DoorKey", "Blocked box", "Box carry")
HEADROOM = {"DoorKey": 1.7, "Blocked box": 0.8, "Box carry": 0.6}  # cm above a drawing's top state


def reward_text(reward):
    return "$0$" if reward == 0 else f"${reward:+g}$"


def arrow_label(arrow):
    """Its reward (or ``mixed``) and, when it holds several transitions, how many."""
    text = "mixed" if len(arrow["rewards"]) > 1 else reward_text(arrow["rewards"][0])
    return text + (f" $(\\times{arrow['count']})$" if arrow["count"] > 1 else "")


def arrow_colour(rewards):
    """``_edge_class`` of ``render-rm``: red if it only costs, green if it pays, else grey."""
    if any(r < 0 for r in rewards):
        return "plotZero" if any(r > 0 for r in rewards) else "plotNeg"
    return "plotPos" if any(r > 0 for r in rewards) else "plotZero"


def drawing(card, arm, machine, origin):
    """TeX lines of one machine at ``origin`` (cm); returns them with the drawing's height."""
    positions, shapes = LAYOUT[card, arm]
    ox, oy = origin
    tag = f"{card[:2]}{arm[0]}".replace(" ", "")
    lines = []
    for state in machine["states"]:
        x, y = positions[state]
        options = ["state"]
        if state == machine["initial"]:
            options.append("initial")
        if state in machine["final"]:
            options.append("accepting")
        if state in machine["rejecting"]:
            options.append("fill=gray!30")
        lines.append(
            f"\\node[{', '.join(options)}] ({tag}{state}) at ({ox + x:.2f},{oy + y:.2f}) {{{state}}};"
        )
    for arrow in machine["arrows"]:
        source, target = arrow["source"], arrow["target"]
        route, place = shapes.get(f"{source}>{target}", ("", "above"))
        colour = arrow_colour(arrow["rewards"])
        label = f"node[{place}, font=\\scriptsize, fill=white, inner sep=1pt, text={colour}] {{{arrow_label(arrow)}}}"
        if source == target:
            lines.append(f"\\path[->, {colour}] ({tag}{source}) edge[{route}] {label} ();")
        else:
            lines.append(
                f"\\draw[->, {colour}] ({tag}{source}) to[{route}] {label} ({tag}{target});"
            )
    ys = [y for _, y in positions.values()]
    return lines, max(ys) - min(ys)


def fig_machines(machines):
    """machines: {(card, arm): merged_arrows(bundle)}; the whole figure as one ``tikzpicture``."""
    lines = [
        "\\begin{tikzpicture}[farm graph, every state/.style={minimum size=7mm, inner sep=1pt}, "
        "every edge/.style={draw}, thick]",
        "\\node[anchor=south, font=\\small\\bfseries] at (2.9,0.1) {FARM};",
        f"\\node[anchor=south, font=\\small\\bfseries] at ({COLUMN['arm-fm'] + 3.0:.2f},0.1) {{ARM-FM}};",
    ]
    y = -0.1
    for card in CARDS:
        title_y = y - 0.2
        lines.append(
            f"\\node[anchor=west, font=\\small\\bfseries] at ({LEFT + 0.55:.2f},{title_y:.2f}) {{{card}}};"
        )
        top = (
            title_y - TITLE_GAP - HEADROOM[card]
        )  # room for arcs and loops above the first row of states
        drawn = []
        for arm in ("farm", "arm-fm"):
            positions = LAYOUT[card, arm][0]
            highest = max(py for _, py in positions.values())
            part, height = drawing(card, arm, machines[card, arm], (COLUMN[arm], top - highest))
            lines += part
            drawn.append(height)
        y = top - max(drawn) - 0.9 - ROW_GAP
        lines.append(
            f"\\draw[black!15, thin] ({LEFT},{y + ROW_GAP / 2:.2f}) -- ({RIGHT},{y + ROW_GAP / 2:.2f});"
        )
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines) + "\n"
