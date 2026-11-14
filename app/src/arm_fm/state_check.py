"""State check before a zero-shot test: do the test machine's states look like the training ones?

A policy reads the embedding of the current RM state. Tested on a machine it never trained on,
it can only transfer if the new states sit near states it knows. The check lists every machine's
states with their descriptions, finds each test state's nearest training state by cosine
similarity, and projects all embeddings to two PCA components (the paper's Fig. 11b).
"""

import json
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go

from .artifacts import load_bundle
from .evaluation import EMBEDDING_IDENTITY

ROLES = ("train", "test", "product")
# The page palette of the figures skill: series colours by role, light and dark.
PALETTE = {
    "light": {
        "card": "#ffffff",
        "text": "#1d1d1f",
        "line": "#5b5b66",
        "series": ["#2f5bd3", "#d96f00", "#1f7a4d"],
    },
    "dark": {
        "card": "#1d1d21",
        "text": "#ececf0",
        "line": "#b9b9c4",
        "series": ["#8fb0ff", "#ffa24d", "#5fd394"],
    },
}
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
# Runs in the saved HTML once the plot is drawn: applies the theme the page (or the system) asks for.
THEME_SCRIPT = """
const gd = document.getElementById("{plot_id}");
const asked = new URLSearchParams(location.search).get("theme");
const dark = asked ? asked === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
const colors = __PALETTE__[dark ? "dark" : "light"];
const grid = colors.line + "40";
const update = {"font.color": colors.text, colorway: colors.series};
for (const axis of ["xaxis", "yaxis"]) {
  for (const key of ["gridcolor", "zerolinecolor", "linecolor", "tickcolor"]) {
    update[axis + "." + key] = grid;
  }
}
document.body.style.margin = 0;
document.documentElement.style.background = colors.card;
document.documentElement.style.colorScheme = dark ? "dark" : "light";
Plotly.relayout(gd, update).then(() => Plotly.Plots.resize(gd));
""".replace("__PALETTE__", json.dumps(PALETTE))
TABLE_TEXT_WIDTH = 90
HOVER_TEXT_WIDTH = 60


@dataclass(frozen=True)
class MachineStates:
    """One bundle's states as the policy sees them."""

    role: str
    name: str  # ``<parent>/<folder>``, so the same card of two arms stays apart
    path: str
    descriptions: dict[str, str]
    vectors: dict[str, np.ndarray]
    embedding: dict[str, Any]  # the embedding settings the bundle records

    def label(self, state: str) -> str:
        return f"{self.name}/{state}"


def load_machine(role: str, directory: Path) -> MachineStates:
    """Read a bundle's state descriptions and embeddings.

    Raises:
        ValueError: If the bundle has no embeddings (a state check needs the vectors).
    """
    bundle = load_bundle(directory)
    if not bundle.embeddings:
        raise ValueError(f"{directory} has no state embeddings")
    vectors = {
        state: np.asarray(vector, dtype=float) for state, vector in bundle.embeddings.items()
    }
    return MachineStates(
        role,
        f"{Path(directory).parent.name}/{Path(directory).name}",
        str(directory),
        dict(bundle.state_descriptions),
        vectors,
        dict(bundle.manifest.effective_settings.get("embedding") or {}),
    )


def check_states(
    train: Sequence[Path], test: Sequence[Path], product: Sequence[Path] = ()
) -> dict[str, Any]:
    """The state check of ``test`` (and ``product``) machines against the ``train`` machines.

    Returns:
        A JSON-ready dict: per machine its state count, descriptions and embedding settings;
        ``problems`` (differing embedding size or settings, a test machine with more states than
        any training one); for each test and product state its nearest training state with the
        cosine; the cosine spread among the training states themselves (each one's nearest other
        training state), for scale; and the PCA points of every state.

    Raises:
        ValueError: If there is no training or no test machine, a bundle is both a training and a
            test (or product) machine, or the embedding sizes differ.
    """
    both = {Path(path).resolve() for path in train} & {
        Path(path).resolve() for path in (*test, *product)
    }
    if both:
        raise ValueError(
            f"a bundle cannot be both a training and a test machine: {sorted(both)[0]}"
        )
    machines = [
        *(load_machine("train", path) for path in train),
        *(load_machine("test", path) for path in test),
        *(load_machine("product", path) for path in product),
    ]
    trained = [machine for machine in machines if machine.role == "train"]
    others = [machine for machine in machines if machine.role != "train"]
    if not trained or not others:
        raise ValueError("a state check needs at least one training machine and one test machine")
    labelled = [
        (machine, state, machine.label(state), vector)
        for machine in machines
        for state, vector in machine.vectors.items()
    ]
    dimensions = {len(vector) for *_, vector in labelled}
    if len(dimensions) > 1:
        raise ValueError(f"the machines' embeddings differ in size: {sorted(dimensions)}")
    unit = {label: vector / np.linalg.norm(vector) for _, _, label, vector in labelled}

    training = [
        (label, unit[label]) for machine, _, label, _ in labelled if machine.role == "train"
    ]
    nearest = []
    for machine, state, label, _ in labelled:
        if machine.role == "train":
            continue
        scores = sorted(
            ((float(unit[label] @ vector), name) for name, vector in training), reverse=True
        )
        nearest.append(
            {
                "role": machine.role,
                "machine": machine.name,
                "state": state,
                "description": machine.descriptions[state],
                "nearest_training_state": scores[0][1],
                "nearest_description": _description_of(trained, scores[0][1]),
                "cosine": scores[0][0],
            }
        )
    neighbours = [
        max(float(vector @ other) for other_name, other in training if other_name != name)
        for name, vector in training
        if len(training) > 1
    ]
    points, variance = _pca([unit[label] for _, _, label, _ in labelled])
    return {
        "machines": [
            {
                "role": machine.role,
                "name": machine.name,
                "path": machine.path,
                "states": len(machine.vectors),
                "embedding": machine.embedding,
                "descriptions": machine.descriptions,
            }
            for machine in machines
        ],
        "problems": _problems(machines),
        "nearest": nearest,
        "training_nearest_other_cosine": (
            {"min": min(neighbours), "mean": float(np.mean(neighbours)), "max": max(neighbours)}
            if neighbours
            else None
        ),
        "pca": {
            "explained_variance_ratio": variance,
            "points": [
                {
                    "label": label,
                    "role": machine.role,
                    "machine": machine.name,
                    "state": state,
                    "x": float(point[0]),
                    "y": float(point[1]),
                    "description": machine.descriptions[state],
                }
                for (machine, state, label, _), point in zip(labelled, points, strict=True)
            ],
        },
    }


def _description_of(trained: Sequence[MachineStates], label: str) -> str:
    return next(
        machine.descriptions[label.removeprefix(f"{machine.name}/")]
        for machine in trained
        if label.startswith(f"{machine.name}/")
    )


def _problems(machines: Sequence[MachineStates]) -> list[str]:
    """What would make a zero-shot test unfair: other embedding settings, more states."""
    problems = []
    reference = machines[0]
    for machine in machines[1:]:
        differing = [
            key
            for key in EMBEDDING_IDENTITY
            if machine.embedding.get(key) != reference.embedding.get(key)
        ]
        if differing:
            problems.append(
                f"{machine.name} was embedded with other settings than {reference.name}: "
                + ", ".join(differing)
            )
    most = max(len(machine.vectors) for machine in machines if machine.role == "train")
    for machine in machines:
        if machine.role != "train" and len(machine.vectors) > most:
            problems.append(
                f"{machine.name} has {len(machine.vectors)} states, more than any training "
                f"machine (at most {most})"
            )
    return problems


def _pca(vectors: Sequence[np.ndarray]) -> tuple[np.ndarray, list[float]]:
    """The first two principal components of ``vectors`` and the variance share each explains."""
    matrix = np.asarray(vectors)
    centred = matrix - matrix.mean(axis=0)
    _, singular, components = np.linalg.svd(centred, full_matrices=False)
    ratio = singular**2 / np.sum(singular**2) if np.sum(singular**2) else singular
    points = centred @ components[:2].T
    if points.shape[1] < 2:  # fewer than two states of spread: pad the missing axis
        points = np.pad(points, ((0, 0), (0, 2 - points.shape[1])))
    return points, [float(value) for value in ratio[:2]]


# ======================================================================================
#                                        OUTPUT
# ======================================================================================


def write_state_check(result: dict[str, Any], output: Path) -> list[Path]:
    """Write ``state-check.json``, ``state-check.md`` and the self-contained ``state-check.html``."""
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / "state-check.json", output / "state-check.md", output / "state-check.html"]
    paths[0].write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    paths[1].write_text(markdown_table(result), encoding="utf-8")
    figure(result).write_html(
        paths[2],
        include_plotlyjs=True,  # one file that opens from disk
        config={"displayModeBar": False},
        post_script=THEME_SCRIPT,
    )
    return paths


def markdown_table(result: dict[str, Any]) -> str:
    """The short table: states per machine, then each test state's nearest training state."""
    lines = ["| role | machine | states | embedding |", "|---|---|---|---|"]
    for machine in result["machines"]:
        settings = machine["embedding"]
        lines.append(
            f"| {machine['role']} | {machine['name']} | {machine['states']} | "
            f"{settings.get('model', '?')} {settings.get('dimension', '?')}d |"
        )
    lines += [
        "",
        "| role | state | nearest training state | cosine | description |",
        "|---|---|---|---|---|",
    ]
    for row in result["nearest"]:
        text = textwrap.shorten(row["description"], TABLE_TEXT_WIDTH, placeholder="...")
        lines.append(
            f"| {row['role']} | {row['machine']}/{row['state']} | {row['nearest_training_state']} | "
            f"{row['cosine']:.3f} | {text} |"
        )
    spread = result["training_nearest_other_cosine"]
    if spread:
        lines += [
            "",
            "Training states' nearest other training state (cosine): "
            f"min {spread['min']:.3f}, mean {spread['mean']:.3f}, max {spread['max']:.3f}.",
        ]
    if result["problems"]:
        lines += ["", "Problems:", *(f"- {problem}" for problem in result["problems"])]
    return "\n".join(lines) + "\n"


def figure(result: dict[str, Any]) -> go.Figure:
    """The 2-D PCA of every state, one trace per role; hover shows the description."""
    cosines = [row["cosine"] for row in result["nearest"]]
    ratio = result["pca"]["explained_variance_ratio"]
    # The title is a claim computed from the data, so a rerun cannot keep a false one.
    title = (
        f"Test states' nearest training state: cosine {min(cosines):.2f} to {max(cosines):.2f}"
        f"<br>PCA of all states, {sum(ratio):.0%} of the variance"
    )
    fig = go.Figure()
    for role in ROLES:
        points = [point for point in result["pca"]["points"] if point["role"] == role]
        if not points:
            continue
        fig.add_trace(
            go.Scatter(
                x=[point["x"] for point in points],
                y=[point["y"] for point in points],
                mode="markers+text",
                name=role,
                text=[
                    f"{point['machine'].rsplit('/', 1)[-1]}/{point['state']}" for point in points
                ],
                # alternate above and below so close states do not print over each other
                textposition=[
                    "top center" if index % 2 == 0 else "bottom center"
                    for index in range(len(points))
                ],
                customdata=[
                    ["<br>".join(textwrap.wrap(point["description"], HOVER_TEXT_WIDTH))]
                    for point in points
                ],
                hovertemplate="%{text}<br>%{customdata[0]}<extra>" + role + "</extra>",
                marker={
                    "size": 11,
                    "symbol": {"train": "circle", "test": "diamond"}.get(role, "square"),
                },
            )
        )
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 15}},
        xaxis_title=f"PC 1 ({ratio[0]:.0%} of variance)",
        yaxis_title=f"PC 2 ({ratio[1]:.0%} of variance)",
        colorway=PALETTE["light"]["series"],
        font={"family": FONT, "color": PALETTE["light"]["text"]},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": -0.2},
    )
    # Room for the labels at the edges, so a narrow screen does not cut them.
    for axis, key in ((fig.update_xaxes, "x"), (fig.update_yaxes, "y")):
        values = [point[key] for point in result["pca"]["points"]]
        pad = 0.2 * (max(values) - min(values) or 1.0)
        axis(range=[min(values) - pad, max(values) + pad])
    return fig
