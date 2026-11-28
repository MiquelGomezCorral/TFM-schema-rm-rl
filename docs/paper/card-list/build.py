r"""The appendix list of the benchmark cards the thesis names, one table grouped by environment.

The thesis names a card by its ID: ``\card{<id>}``, or ``\texttt{<id>}`` while a table has not moved to the macro. A
rewording is named ``<card id>~p<n>``, the n-th entry of the card's ``paraphrases``. This script reads those IDs from
the thesis source, looks each one up in the card files (``experiments/benchmark/<suite>/tasks.json``) and writes a
``longtable`` of ID and task text. Each row carries the link target ``card:<id>`` that ``\card`` points to
(``paper/`` gets the macro from ``R11/preamble.tex``). Each row opens with ``\cardrow{<id>}``, the macro there that
sets the ID and the link target ``card:<id>`` that ``\card`` points to. Stops, and writes nothing, when a ``\card``
names no card and when a named card runs in an environment that ``ENVIRONMENTS`` does not name.

Run from the repository root, with the system python or in RM_RL_env (standard library only):
python3 docs/paper/card-list/build.py --thesis paper/plantillatfg.tex --out paper/images/cards/list.tex
"""

import argparse
import json
import re
import sys
from pathlib import Path

CARD_FILES = Path(__file__).resolve().parents[3] / "experiments" / "benchmark"
# A card in two suites (base-doorkey is in base and pilot) is listed from the first of these; the other suites follow by name.
FIRST_SUITES = ("base", "complex", "templates", "box-carry", "forced-start", "forcing", "shop")

# Environment names as the thesis writes them (Table tab:eval-suites and its text). The key is the environment's
# folder, from the card's env.description, and its env.gym_id, because the folder alone holds KeyCorridor S4R3 and
# S6R3 and the gym_id alone holds the service room and its box-carried copy. The order is the order of the groups.
ENVIRONMENTS = {
    ("minigrid-doorkey", "MiniGrid-DoorKey-8x8-v0"): r"DoorKey 8$\times$8",
    ("minigrid-unlock-pickup", "MiniGrid-UnlockPickup-v0"): "UnlockPickup",
    ("minigrid-blocked-unlock-pickup", "MiniGrid-BlockedUnlockPickup-v0"): "BlockedUnlockPickup",
    ("minigrid-key-corridor", "MiniGrid-KeyCorridorS4R3-v0"): "KeyCorridor S4R3",
    ("minigrid-key-corridor", "MiniGrid-KeyCorridorS6R3-v0"): "KeyCorridor S6R3",
    ("service-room", "MiniGrid-ServiceRoom-v0"): "Service room",
    ("service-room-carry", "MiniGrid-ServiceRoom-v0"): "Service room, box carried",
    ("minigrid-lanes", "MiniGrid-Lanes-v0"): "Zombie lanes",
    ("minigrid-key-gift", "MiniGrid-KeyGift-v0"): "KeyGift",
    (
        "minigrid-unlock-pickup-key-held",
        "MiniGrid-UnlockPickup-KeyHeld-v0",
    ): "UnlockPickup, key held",
    (
        "minigrid-blocked-unlock-pickup-cleared",
        "MiniGrid-BlockedUnlockPickup-Cleared-v0",
    ): "BlockedUnlockPickup, ball moved",
    ("shop", "MiniGrid-Shop-v0"): "Shop",
    ("shop-pot", "MiniGrid-Shop-Pot-v0"): "Shop with a pot",
}
TEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
# The ID column is narrower than the longest ID: it wraps after a hyphen, never inside a word.
RAGGED = r">{\raggedright\arraybackslash}"
COLUMNS = rf"@{{}}{RAGGED}p{{5.4cm}}@{{\hspace{{1em}}}}{RAGGED}p{{\dimexpr\textwidth-5.4cm-1em\relax}}@{{}}"
HEAD = r"\textbf{ID} & \textbf{Task} \\"


def tex_text(text: str) -> str:
    """Plain text as LaTeX: special characters escaped, straight double quotes turned into LaTeX quotes."""
    text = "".join(TEX_SPECIAL.get(char, char) for char in text)
    return re.sub(r'"([^"]*)"', r"``\1''", text)


def undo_tex(text: str) -> str:
    r"""The text that ``\texttt{...}`` shows for an ID: its LaTeX escapes turned back into characters."""
    text = re.sub(r"\\textasciitilde(?:\{\}|\s)?", "~", text)
    text = re.sub(r"\\allowbreak\s?", "", text)
    return text.replace(r"\_", "_")


def named_ids(thesis: Path) -> tuple[set[str], set[str]]:
    r"""The arguments of every ``\card`` and the texts of every ``\texttt`` in the thesis, comments left out."""
    lines = (re.sub(r"(?<!\\)%.*", "", line) for line in thesis.read_text().split("\n"))
    source = "\n".join(lines)
    from_card = set(re.findall(r"\\card\{([^{}]*)\}", source))
    from_texttt = {undo_tex(text) for text in re.findall(r"\\texttt\{((?:[^{}]|\{\})*)\}", source)}
    return from_card, from_texttt


def load_entries() -> dict[str, tuple[tuple[str, str], str]]:
    """Every card and rewording of the card files as ``id -> (environment key, task text)``, in file order."""
    folders = sorted(
        (path.parent.name for path in CARD_FILES.glob("*/tasks.json")),
        key=lambda name: (
            FIRST_SUITES.index(name) if name in FIRST_SUITES else len(FIRST_SUITES),
            name,
        ),
    )
    entries = {}
    for folder in folders:
        for card in json.loads((CARD_FILES / folder / "tasks.json").read_text())["cards"]:
            if card["id"] in entries:
                continue
            env = (Path(card["env"]["description"]).parent.name, card["env"]["gym_id"])
            entries[card["id"]] = (env, card["task"])
            for number, text in enumerate(card.get("paraphrases", []), 1):
                entries[f"{card['id']}~p{number}"] = (env, text)
    return entries


def render(groups: dict[str, list[tuple[str, str]]]) -> str:
    """The longtable: a head row that repeats, then one rule and one bold heading row per environment."""
    lines = [
        "% Generated by docs/paper/card-list/build.py from the card files. Do not edit.",
        r"{\footnotesize\renewcommand{\arraystretch}{1.2}",
        r"\begin{longtable}{" + COLUMNS + "}",
        r"\caption{The tasks named in the thesis, by environment.}\label{tab:app-cards}\\",
        rf"\toprule {HEAD} \midrule \endfirsthead",
        rf"\toprule {HEAD} \midrule \endhead",
        r"\bottomrule \endfoot",
    ]
    for index, (name, rows) in enumerate(groups.items()):
        lines += [
            r"\midrule" if index else "",
            rf"\multicolumn{{2}}{{@{{}}l}}{{\textbf{{{name}}}}} \\*",
        ]
        body = [rf"\cardrow{{{card_id}}} & {tex_text(task)} \\" for card_id, task in rows]
        if index < len(groups) - 1:
            body[-1] += "*"  # no page break before the next rule: a page never ends on a lone rule
        lines += body
    return "\n".join(line for line in lines if line) + "\n" + r"\end{longtable}}" + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the appendix list of the cards the thesis names."
    )
    parser.add_argument("--thesis", type=Path, required=True, help="the thesis .tex file")
    parser.add_argument("--out", type=Path, required=True, help="the LaTeX file to write")
    args = parser.parse_args()

    entries = load_entries()
    from_card, from_texttt = named_ids(args.thesis)
    unknown = sorted(from_card - entries.keys())
    if unknown:
        sys.exit("error: \\card names no card or rewording: " + ", ".join(unknown))

    named = from_card | (from_texttt & entries.keys())
    rows = [(card_id, *entries[card_id]) for card_id in entries if card_id in named]
    unnamed = {
        f"{card_id} ({env[0]}, {env[1]})" for card_id, env, _ in rows if env not in ENVIRONMENTS
    }
    if unnamed:
        sys.exit("error: no environment name in ENVIRONMENTS for: " + ", ".join(sorted(unnamed)))

    groups = {}
    for env, name in ENVIRONMENTS.items():
        group = [(card_id, task) for card_id, key, task in rows if key == env]
        if group:
            groups[name] = group
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(groups))
    print(f"card list: {len(rows)} cards in {len(groups)} environments")


if __name__ == "__main__":
    main()
