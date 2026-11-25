r"""TeX of the Results figures 1 to 4 (pgfplots axes, shapes drawn in axis coordinates).

Every function takes the rows ``make_figures.py`` computed and returns the text of one figure file:
one ``tikzpicture`` sized for ``\textwidth``, colours from ``fig-palette.tex``. The arm colours,
shades and hatches are the palette's one scheme: solid = learned or built at the first round,
light = built after a further round, open = built but not learned, hatched = not built.
"""

from math import ceil

ARM_COLOR = {"farm": "plotFarm", "arm-fm": "plotArm", "no-rm": "plotNoRm"}
ARM_LIGHT = {"farm": "plotFarmLight", "arm-fm": "plotArmLight", "no-rm": "plotNoRmLight"}
ARM_NAME = {"farm": "FARM", "arm-fm": "ARM-FM", "no-rm": "no RM"}
HATCH = "pattern=north east lines, pattern color={}"
FILL_OUTLINE = "black!55, line width=0.3pt"


def cs(x, y):
    return f"(axis cs:{x:.4f},{y:.4f})"


def box(x0, y0, x1, y1, style):
    return f"\\path[{style}] {cs(x0, y0)} rectangle {cs(x1, y1)};"


def node(x, y, text, style):
    return f"\\node[{style}] at {cs(x, y)} {{{text}}};"


def line(points, style):
    return f"\\draw[{style}] " + " -- ".join(cs(x, y) for x, y in points) + ";"


def pct(share, digits=1):
    return f"{100 * share:.{digits}f}\\%"


def swatch(style):
    return f"\\addlegendimage{{area legend, {style}}}"


def parts_swatch(styles):
    """A legend swatch cut into one part per style, so a shade shows in every arm colour."""
    step = 0.6 / len(styles)
    parts = "".join(
        f"\\draw[{style}] ({i * step:.2f}cm,-0.1cm) rectangle ({(i + 1) * step:.2f}cm,0.1cm);"
        for i, style in enumerate(styles)
    )
    return f"\\addlegendimage{{legend image code/.code={{{parts}}}}}"


def shade_styles(arm):
    """Fill styles of a bar of one arm: built first, built after a further round, not built."""
    base = ARM_COLOR[arm]
    return [
        f"fill={base}, draw={FILL_OUTLINE}",
        f"fill={ARM_LIGHT[arm]}, draw={FILL_OUTLINE}",
        f"{HATCH.format(base)}, draw={FILL_OUTLINE}",
    ]


def picture(axis_options, body, left, right=0.0):
    r"""Return one tikzpicture whose axis keeps ``left`` and ``right`` cm of the text width free.

    They hold what hangs outside the plot area (tick labels, axis label, side notes), so the whole
    picture fits ``\textwidth``; pgfplots' ``width`` is the plot area only.
    """
    width = f"scale only axis, width=\\dimexpr\\textwidth-{left + right}cm\\relax"
    return "\n".join(
        [
            "\\begin{tikzpicture}",
            f"\\begin{{axis}}[res axis, {width}, {axis_options}]",
            *body,
            "\\end{axis}",
            "\\end{tikzpicture}",
            "",
        ]
    )


# ========= Figure 1: machines built per arm =========
def fig_built(rows):
    """rows: {arm: dict(asked, first, further, not_built, built, low, high, detail)}; share = built/asked."""
    asked = rows["farm"]["asked"]
    y = {"farm": 1.6, "arm-fm": 0.0}
    half = 0.22
    body = []
    meanings = (
        "built at the first round or try",
        "built after a further round or attempts",
        "not built",
    )
    for shade, meaning in enumerate(meanings):
        body += [
            parts_swatch([shade_styles(arm)[shade] for arm in rows]),
            f"\\addlegendentry{{{meaning}}}",
        ]
    for arm, row in rows.items():
        edges = [0, row["first"], row["first"] + row["further"], asked]
        for start, end, style in zip(
            edges, edges[1:], shade_styles(arm), strict=False
        ):  # pairs: one fewer than edges
            body.append(box(start, y[arm] - half, end, y[arm] + half, style))
        whisker_y = y[arm] - half - 0.2
        body += [
            line(
                [(row["low"] * asked, whisker_y), (row["high"] * asked, whisker_y)],
                "black, line width=0.6pt",
            ),
            line(
                [(row["low"] * asked, whisker_y - 0.05), (row["low"] * asked, whisker_y + 0.05)],
                "black, line width=0.6pt",
            ),
            line(
                [(row["high"] * asked, whisker_y - 0.05), (row["high"] * asked, whisker_y + 0.05)],
                "black, line width=0.6pt",
            ),
            f"\\fill[black] {cs(row['built'], whisker_y)} circle (1.3pt);",
        ]
    farm, armfm = rows["farm"], rows["arm-fm"]
    body += [
        node(farm["first"] / 2, y["farm"], str(farm["first"]), "font=\\footnotesize, text=white"),
        node(
            armfm["first"] / 2, y["arm-fm"], str(armfm["first"]), "font=\\footnotesize, text=white"
        ),
        node(
            armfm["first"] + armfm["further"] / 2,
            y["arm-fm"],
            str(armfm["further"]),
            "font=\\footnotesize",
        ),
        node(
            armfm["built"] + armfm["not_built"] / 2,
            y["arm-fm"],
            str(armfm["not_built"]),
            "font=\\footnotesize, fill=white, inner sep=1.5pt",
        ),
    ]
    # FARM's thin segments are too narrow to see (1 to 3 of 266 machines): one enlarged cell per
    # machine above the bar's end, tied to the segments by two lines
    cell, rise, depth = 6.0, 0.14, 0.3  # axis units
    shades = [1] * farm["further"] + [2] * farm["not_built"]
    left, top = asked - cell * len(shades), y["farm"] + half
    tie = "black!60, line width=0.3pt"
    body += [
        line([(farm["first"], top), (left, top + rise)], tie),
        line([(asked, top), (asked, top + rise)], tie),
        *(
            box(
                left + i * cell,
                top + rise,
                left + (i + 1) * cell,
                top + rise + depth,
                shade_styles("farm")[shade],
            )
            for i, shade in enumerate(shades)
        ),
        node(
            left - 2,
            top + rise + depth / 2,
            f"{farm['further']} after a further round, {farm['not_built']} not built",
            "anchor=east, font=\\scriptsize, inner sep=1.5pt",
        ),
    ]
    # ARM-FM's split of its further attempts is named above its bar
    middle = armfm["first"] + armfm["further"] / 2
    body.append(
        line(
            [(middle, y["arm-fm"] + half), (middle, y["arm-fm"] + half + 0.12)],
            "black!60, line width=0.3pt",
        )
    )
    body.append(
        node(
            middle,
            y["arm-fm"] + half + 0.12,
            f"{armfm['further']} after further attempts: {armfm['detail']}",
            "anchor=south, font=\\scriptsize, inner sep=1.5pt",
        )
    )
    for arm, row in rows.items():
        label = f"{pct(row['built'] / asked)} built\\\\95\\% interval {pct(row['low'])} to {pct(row['high'])}"
        wy = y[arm] - half - 0.2
        if arm == "farm":
            body.append(
                node(
                    row["low"] * asked - 3, wy, label, "anchor=east, align=right, font=\\scriptsize"
                )
            )
        else:
            body.append(
                node(
                    row["high"] * asked + 3, wy, label, "anchor=west, align=left, font=\\scriptsize"
                )
            )
    options = (
        # xmax leaves room right of the last bar for FARM's interval end (99.9% of 266)
        f"height=5.8cm, xmin=0, xmax={asked + 8}, ymin=-0.8, ymax=2.5, "
        "ytick={0,1.6}, yticklabels={ARM-FM,FARM}, ytick style={draw=none}, "
        f"xtick={{0,50,100,150,200,250}}, extra x ticks={{{asked}}}, "
        f"xlabel={{RMs built, of {asked} asked per arm}}, "
        "legend style={at={(0.5,-0.25)}, anchor=north, legend columns=1}"
    )
    return picture(options, body, left=2.0)


# ========= Figure 2: rows learned per arm and group =========
def fig_learned(rows, groups, names):
    """rows: dicts group, arm, n, learned, not_learned, not_built, low, high (shares 0 to 1)."""
    offsets = {"farm": -0.28, "arm-fm": 0.0, "no-rm": 0.28}
    width = 0.24
    body = []
    for arm in ("farm", "arm-fm", "no-rm"):
        body += [
            swatch(f"fill={ARM_COLOR[arm]}, draw={ARM_COLOR[arm]}"),
            f"\\addlegendentry{{{ARM_NAME[arm]}}}",
        ]
    # the status swatches are cut into the three arm colours, so none matches the grey of "no RM"
    status = {
        "learned": lambda base: f"fill={base}, draw={FILL_OUTLINE}",
        "trained, not learned": lambda base: f"fill=white, draw={base}, line width=0.3pt",
        "RM not built": lambda base: f"{HATCH.format(base)}, draw={base}, line width=0.3pt",
    }
    for meaning, style in status.items():
        body += [
            parts_swatch([style(ARM_COLOR[arm]) for arm in ARM_COLOR]),
            f"\\addlegendentry{{{meaning}}}",
        ]
    for row in rows:
        gx = groups.index(row["group"]) + 1 + offsets[row["arm"]]
        n = row["n"]
        learned = 100 * row["learned"] / n
        trained = 100 * (row["learned"] + row["not_learned"]) / n
        base = ARM_COLOR[row["arm"]]
        x0, x1 = gx - width / 2, gx + width / 2
        body += [
            box(x0, 0, x1, learned, f"fill={base}, draw={FILL_OUTLINE}"),
            box(x0, learned, x1, trained, f"fill=white, draw={base}, line width=0.3pt"),
            box(x0, trained, x1, 100, f"{HATCH.format(base)}, draw={base}, line width=0.3pt"),
            line([(gx, 100 * row["low"]), (gx, 100 * row["high"])], "black, line width=0.6pt"),
            line(
                [(gx - 0.05, 100 * row["low"]), (gx + 0.05, 100 * row["low"])],
                "black, line width=0.6pt",
            ),
            line(
                [(gx - 0.05, 100 * row["high"]), (gx + 0.05, 100 * row["high"])],
                "black, line width=0.6pt",
            ),
            node(
                gx,
                max(100, 100 * row["high"]) + 1.5,
                str(row["learned"]),
                "anchor=south, font=\\scriptsize, inner sep=1pt",
            ),
        ]
    labels = ",".join(
        f"{{{names[g]}\\\\(n={next(r['n'] for r in rows if r['group'] == g)})}}" for g in groups
    )
    options = (
        "height=7cm, xmin=0.45, xmax=5.55, ymin=0, ymax=116, "
        f"xtick={{1,2,3,4,5}}, xticklabels={{{labels}}}, xticklabel style={{align=center}}, xtick style={{draw=none}}, "
        "ytick={0,20,40,60,80,100}, yticklabel={\\pgfmathprintnumber{\\tick}\\%}, "
        "ylabel={tasks learned (95\\% Wilson interval)}, ymajorgrids, major grid style={black!12}, "
        "legend style={at={(0.5,1.04)}, anchor=south, legend columns=3}"
    )
    return picture(options, body, left=1.9)


# ========= Figure 3: soft breaks per judged episode =========
def fig_soft(panels, xmax):
    """panels: [(title, rows)]; a row: label, idle, and per arm None or dict(mean, low, high, seeds)."""
    offsets = {"farm": -0.25, "arm-fm": 0.0, "no-rm": 0.25}
    height = 0.2
    body = [
        swatch(f"fill={ARM_COLOR['farm']}, draw={ARM_COLOR['farm']}"),
        "\\addlegendentry{FARM}",
        swatch(f"fill={ARM_COLOR['arm-fm']}, draw={ARM_COLOR['arm-fm']}"),
        "\\addlegendentry{ARM-FM}",
        swatch(f"fill={ARM_COLOR['no-rm']}, draw={ARM_COLOR['no-rm']}"),
        "\\addlegendentry{no RM}",
        "\\addlegendimage{only marks, mark=*, mark size=1.2pt, mark options={fill=black, draw=white, line width=0.3pt}}",
        "\\addlegendentry{one run}",
        "\\addlegendimage{only marks, mark=|, mark size=4pt, mark options={line width=1.2pt}}",
        "\\addlegendentry{idle plan}",
    ]
    ticks, labels, y = [], [], 0.0
    for title, rows in panels:
        y += 1.0
        body.append(node(-0.4, y, f"\\textbf{{{title}}}", "anchor=west, font=\\scriptsize"))
        y += 0.2
        for row in rows:
            y += 1.0
            ticks.append(y)
            labels.append(row["label"])
            for arm in ("farm", "arm-fm", "no-rm"):
                data = row[arm]
                yy = y + offsets[arm]
                if (
                    data is None
                ):  # in a column right of the frame, clear of the bars and the idle mark
                    body.append(
                        node(
                            xmax + 0.5,
                            yy,
                            "not built",
                            f"anchor=west, font=\\scriptsize, text={ARM_COLOR[arm]}",
                        )
                    )
                    continue
                body.append(
                    box(
                        0,
                        yy - height / 2,
                        data["mean"],
                        yy + height / 2,
                        f"fill={ARM_COLOR[arm]}, draw=none",
                    )
                )
                if data["high"] > data["low"]:
                    cap = height / 2
                    body += [
                        line([(data["low"], yy), (data["high"], yy)], "black, line width=0.5pt"),
                        line(
                            [(data["low"], yy - cap), (data["low"], yy + cap)],
                            "black, line width=0.5pt",
                        ),
                        line(
                            [(data["high"], yy - cap), (data["high"], yy + cap)],
                            "black, line width=0.5pt",
                        ),
                    ]
                body += [
                    f"\\filldraw[fill=black, draw=white, line width=0.3pt] {cs(value, yy)} circle (1.2pt);"
                    for value in data["seeds"]
                ]
            if row["idle"] is not None:
                body.append(
                    line(
                        [(row["idle"], y - 0.45), (row["idle"], y + 0.45)],
                        "black, line width=1.2pt",
                    )
                )
    body.append(line([(0, 0.4), (0, y + 0.6)], "black!45, line width=0.4pt"))
    options = (
        f"clip=false, height={0.62 * y + 1.0:.2f}cm, xmin=-1, xmax={xmax}, ymin=0.4, ymax={y + 0.6:.2f}, y dir=reverse, "
        f"ytick={{{','.join(f'{v:.2f}' for v in ticks)}}}, yticklabels={{{','.join(labels)}}}, "
        f"yticklabel style={{font=\\scriptsize}}, ytick style={{draw=none}}, xtick={{{','.join(map(str, range(0, xmax, 5)))}}}, "
        "xlabel={soft breaks per judged episode (every broken step)}, xmajorgrids, major grid style={black!10}, "
        "legend style={at={(0.5,-0.1)}, anchor=north, legend columns=5}"
    )
    return picture(options, body, left=4.6, right=1.5)


# ========= Figure 4: right machines per thinking level, per model =========
def mark_size(mark):
    """A triangle of the circle's radius looks smaller, so it gets a larger one."""
    return {"triangle*": "3.2pt"}.get(mark, "2.6pt")


def fig_thinking(rows, labels):
    """rows: dicts series, colour, mark, level, runs, right, median_s, low, high (0 to 1), beaten.

    One colour and one mark per series; whiskers and level labels take the series colour. A point no
    other point beats is filled, a beaten one hollow, and a thin grey line joins the filled points in
    order of time. The axes reach every point and whisker. labels: {(series, level): (node anchor, "point", "low" or "high" (the end of the
    interval the node hangs on), (dx, dy) shift of the node from there, in pt)}; each label sits
    beside its own point, where the neighbouring points, whiskers and grey line leave room.
    """
    body = []
    for name, colour, mark in dict.fromkeys((r["series"], r["colour"], r["mark"]) for r in rows):
        body += [
            f"\\addlegendimage{{only marks, mark={mark}, mark size={mark_size(mark)}, color={colour}, "
            f"mark options={{fill={colour}, draw=white, line width=0.4pt}}}}",
            f"\\addlegendentry{{{name}}}",
        ]
    frontier = sorted((r for r in rows if not r["beaten"]), key=lambda r: r["median_s"])
    points = [(r["median_s"], 100 * r["right"] / r["runs"]) for r in frontier]
    body.append(line(points, "black!35, line width=0.4pt"))
    for row in rows:
        x, y = row["median_s"], 100 * row["right"] / row["runs"]
        low, high = 100 * row["low"], 100 * row["high"]
        colour = row["colour"]
        whisker = f"{colour}, line width=0.6pt"
        if row["beaten"]:
            mark_options = f"fill=white, draw={colour}, line width=0.9pt"
        else:
            mark_options = f"fill={colour}, draw=white, line width=0.4pt"
        anchor, hang, (dx, dy) = labels[row["series"], row["level"]]
        body += [
            line([(x, low), (x, high)], whisker),
            line([(x * 0.98, low), (x * 1.02, low)], whisker),
            line([(x * 0.98, high), (x * 1.02, high)], whisker),
            f"\\addplot[only marks, forget plot, mark={row['mark']}, mark size={mark_size(row['mark'])}, "
            f"color={colour}, mark options={{{mark_options}}}] coordinates {{({x:.3f},{y:.3f})}};",
            node(
                x,
                {"point": y, "low": low, "high": high}[hang],
                row["level"],
                f"anchor={anchor}, xshift={dx}pt, yshift={dy}pt, text={colour}, font=\\scriptsize, "
                "inner sep=1pt",
            ),
        ]
    xmin, xmax = 0.87 * min(r["median_s"] for r in rows), 1.15 * max(r["median_s"] for r in rows)
    ymin = 100 * min(r["low"] for r in rows) - 2.5
    yticks = ",".join(str(v) for v in range(5 * ceil(ymin / 5), 101, 5))
    options = (
        f"height=8cm, xmode=log, log ticks with fixed point, xmin={xmin:.2f}, xmax={xmax:.2f}, "
        f"ymin={ymin:.1f}, ymax=104, xtick={{4,10,20,50,100}}, ytick={{{yticks}}}, "
        "yticklabel={\\pgfmathprintnumber{\\tick}\\%}, "
        "xlabel={median seconds to generate one RM}, ylabel={share of right RMs, of 138 runs (95\\% Wilson interval)}, "
        "ymajorgrids, xmajorgrids, major grid style={black!12}, "
        "legend style={at={(0.5,1.04)}, anchor=south, legend columns=3}"
    )
    return picture(options, body, left=2.0)


# ========= Figures 6 and 7: judged success per task on the ARM-FM paper's tasks =========
def fig_armfm(groups, sections):
    """groups: [(tick label, {arm: cell})]; sections: [(first group, last group, heading)], 1-based.

    A cell has mean, low, high and either ``runs`` (the judged success of each run, drawn as dots,
    interval over runs) or ``count`` = (runs judged successful, runs), a share drawn as a light bar
    with a dashed interval and its count above.
    """
    step, half, cap = 0.27, 0.11, 0.04
    arms = ("farm", "arm-fm", "no-rm")
    offsets = {arm: (i - 1) * step for i, arm in enumerate(arms)}
    whisker = "black, line width=0.6pt"
    body = []
    for arm in arms:
        body += [
            swatch(f"fill={ARM_COLOR[arm]}, draw={FILL_OUTLINE}"),
            f"\\addlegendentry{{{ARM_NAME[arm]}}}",
        ]
    body += [
        "\\addlegendimage{only marks, mark=*, mark size=1.4pt, mark options={fill=black, draw=white, line width=0.3pt}}",
        "\\addlegendentry{one run}",
        f"\\addlegendimage{{{whisker}}}",
        "\\addlegendentry{95\\% $t$ interval}",
    ]
    if any("count" in cell for _, cells in groups for cell in cells.values()):
        share = (
            "\\draw[fill=black!15, draw=black!55, line width=0.3pt] (0.15cm,-0.1cm) rectangle (0.45cm,0.1cm);"
            "\\draw[black, dashed, line width=0.6pt] (0.3cm,-0.15cm) -- (0.3cm,0.15cm);"
        )
        body += [
            f"\\addlegendimage{{legend image code/.code={{{share}}}}}",
            "\\addlegendentry{share of runs judged successful, 95\\% Wilson interval}",
        ]
    for gx, (_, cells) in enumerate(groups, start=1):
        for arm, cell in cells.items():
            x = gx + offsets[arm]
            counted = "count" in cell
            fill = ARM_LIGHT[arm] if counted else ARM_COLOR[arm]
            body.append(
                box(x - half, 0, x + half, cell["mean"], f"fill={fill}, draw={FILL_OUTLINE}")
            )
            if cell["high"] > cell["low"]:
                body += [
                    line(
                        [(x, cell["low"]), (x, cell["high"])],
                        whisker + (", dashed" if counted else ""),
                    ),
                    line([(x - cap, cell["low"]), (x + cap, cell["low"])], whisker),
                    line([(x - cap, cell["high"]), (x + cap, cell["high"])], whisker),
                ]
            if counted:
                successes, runs = cell["count"]
                body.append(
                    node(
                        x,
                        cell["high"] + 0.01,
                        f"{successes}/{runs}",
                        "anchor=south, font=\\scriptsize",
                    )
                )
                continue
            body += [
                f"\\filldraw[fill=black, draw=white, line width=0.3pt] {cs(x + dx, value)} circle (1.4pt);"
                for dx, value in zip((-0.06, 0.0, 0.06), cell["runs"], strict=True)
            ]
    for first, last, heading in sections:
        body.append(node((first + last) / 2, 1.03, heading, "anchor=south, font=\\scriptsize"))
        if first > 1:
            body.append(
                line([(first - 0.5, 0), (first - 0.5, 1.16)], "black!40, dashed, line width=0.4pt")
            )
    n = len(groups)
    labels = ",".join(f"{{{label}}}" for label, _ in groups)
    options = (
        f"height=6cm, xmin=0.45, xmax={n + 0.55}, ymin=0, ymax=1.16, "
        f"xtick={{{','.join(str(i) for i in range(1, n + 1))}}}, xticklabels={{{labels}}}, "
        "xticklabel style={align=center, font=\\scriptsize}, xtick style={draw=none}, "
        "ytick={0,0.2,0.4,0.6,0.8,1}, yticklabel style={/pgf/number format/fixed, /pgf/number format/precision=1}, "
        "ylabel={judged success}, ymajorgrids, major grid style={black!12}, "
        "legend style={at={(0.5,1.03)}, anchor=south, legend columns=3}"
    )
    return picture(options, body, left=1.6)
