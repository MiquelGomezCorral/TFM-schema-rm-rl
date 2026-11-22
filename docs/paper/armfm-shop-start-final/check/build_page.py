"""Build ``data.json`` of the armfm-shop-start-final entry from its evidence copies.

Reads the 23 finished ARM-FM shop bundles copied from ``experiments/benchmark/shop/bundles-freeze/arm-fm``
(packed in ``evidence/bundles-freeze.tar.gz``: machine, manifest, status and plan check of each) and the gate records
of the 22 that were gated (``evidence/gate``). Start and final states come from each machine's own text; tasks and the
card's clauses from the shop cards.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/armfm-shop-start-final/check/build_page.py
"""

import json
import math
import tarfile
from pathlib import Path

from src.benchmark import load_cards
from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
# packed so the repo's format hooks leave the ARM-FM labeling.py copies byte-exact
COPIES = ENTRY / "evidence/bundles-freeze.tar.gz"
GATE = ENTRY / "evidence/gate/shop"
CARDS = ROOT / "experiments/benchmark/shop/tasks.json"
SHOWN = ("shop-siren", "shop-pot", "shop-serve")
GATE_READS = {  # what the gate's read of each main machine found besides the final start (armfm-shop-gate.md)
    "shop-siren": "Otherwise a right Response machine: a ring owes a toggle, and the toggle pays 1.",
    "shop-pot": "Otherwise a right Response machine: a boil owes a fix, and the fix pays 1.",
    "shop-serve": "Also a fall not picked up on the next move only costs 0.1 per step: the hard rule became soft.",
}
MAIN_ORDER = (
    "029d82c",
    "e37dff9",
    "2c267e1",
    "03905e4",
    "04fd146",
    "881b22d",
)  # git log --first-parent main
Z95 = 1.959964


def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def packed_texts() -> dict[str, str]:
    """Text of each machine, manifest and status file in the packed copies, by path under ``arm-fm/``."""
    with tarfile.open(COPIES) as tar:
        return {
            member.name.removeprefix("bundles-freeze/arm-fm/"): tar.extractfile(member)
            .read()
            .decode()
            for member in tar.getmembers()
            if member.isfile() and member.name.endswith((".txt", ".json"))
        }


def machine(name: str, files: dict[str, str]) -> dict:
    """Header fields and counts of one bundle's machine, read as ``summary.py`` reads them."""
    text = files[f"{name}/reward_machine.txt"]
    lines = text.splitlines()
    field = {
        k.strip(): v.strip() for k, _, v in (line.partition(":") for line in lines) if v.strip()
    }
    manifest = json.loads(files[f"{name}/manifest.json"])
    status = json.loads(files[f"{name}.status.json"])
    gate_path = GATE / f"{name}.armfm_gate.json"
    return {
        "name": name,
        "card": name.split("~")[0],
        "wording": name.split("~")[1] if "~" in name else "card",
        "text": text,
        "task": manifest["task"],
        "commit": manifest["provenance"]["stamp"]["commit"][:7],
        "states": [s.strip() for s in field["STATES"].split(",")],
        "start": field["INITIAL_STATE"],
        "finals": [s.strip() for s in field["FINAL_STATES"].split(",")],
        "transitions": sum(
            1 for line in lines if line.startswith("(") and line.split(")")[0].count(",") == 1
        ),
        "status": status["reason"],
        "gate": json.loads(gate_path.read_text()) if gate_path.is_file() else None,
    }


def bundle_row(m: dict) -> list:
    start_final = m["start"] in m["finals"]
    gate = m["gate"]
    return [
        f"`{m['name']}`",
        m["wording"],
        f"{len(m['states'])} / {m['transitions']}",
        f"{m['start']} / {', '.join(m['finals'])}",
        {"text": "yes" if start_final else "no", "tone": "bad" if start_final else "warn"},
        m["status"].removeprefix("plan-check-failed: "),
        "not gated" if gate is None else ("passed" if gate["passed"] else "failed"),
        f"`{m['commit']}`",
    ]


def card_clauses(card) -> list[list[str]]:
    return [
        [f"{t}({', '.join(names)}) {priority}", f"`{pretty_ltlf(ltlf_of(t, list(names)))}`"]
        for t, names, priority in card.expect
    ]


def machine_item(m: dict, card, note: str) -> dict:
    gate = m["gate"]
    return {
        "title": f"{m['name']}: {len(m['states'])} states, final {', '.join(m['finals'])}",
        "preview": "starts final" if m["start"] in m["finals"] else "early final",
        "open": m["name"] == "shop-siren",
        "blocks": [
            {"type": "text", "text": f"**Task:** {m['task']}"},
            {
                "type": "table",
                "heading": "The card's answer (ARM-FM writes no clauses, so this is what a right machine must do)",
                "columns": ["Clause", "LTLf"],
                "rows": card_clauses(card),
            },
            {
                "type": "figure",
                "src": f"graphs/{m['name']}.html",
                "height": 440,
                "caption": f"The ARM-FM machine: start {m['start']}, final {', '.join(m['finals'])}. "
                f"{note} Drag a state, click an edge for its cases.",
            },
            {
                "type": "details",
                "items": [{"title": "RM text", "blocks": [{"type": "code", "text": m["text"]}]}],
            },
            {
                "type": "table",
                "heading": "Gate, seed 1 of seeds 1-5 and 42 (all six seeds give the same problems)",
                "columns": ["Check", "Result"],
                "rows": [
                    ["Plan check", "; ".join(gate["plan_check"]["problems"]["1"])],
                    ["Pay order", gate["pay_order"]["output"].split(": ", 1)[1]],
                    [
                        "Facts, labeling",
                        "pass" if gate["facts"]["ok"] and gate["labeling"]["ok"] else "fail",
                    ],
                ],
            },
        ],
    }


def build() -> dict:
    cards = {card.id: card for card in load_cards(CARDS).cards}
    files = packed_texts()
    names = sorted(
        path.removesuffix(".status.json")
        for path in files
        if "/" not in path and path.endswith(".status.json")
    )
    machines = {name: machine(name, files) for name in names}
    gated = [m for m in machines.values() if m["gate"] is not None]
    start_final = [m for m in gated if m["start"] in m["finals"]]
    early = [m for m in gated if m["start"] not in m["finals"]]
    assert not any(m["gate"]["passed"] for m in gated), "a gated bundle passes now"
    assert [m["name"] for m in early] == ["shop-boil~p3"], [m["name"] for m in early]
    low, high = wilson(len(start_final), len(gated))
    boil = machines["shop-boil~p3"]
    commits = sorted({m["commit"] for m in machines.values()}, key=MAIN_ORDER.index)
    items = [machine_item(machines[name], cards[name], GATE_READS[name]) for name in SHOWN]
    boil_item = machine_item(
        boil,
        cards["shop-boil"],
        "Every state steps to the final on a served order, so the first serve ends the episode whatever is "
        "still owed.",
    )
    return {
        "eyebrow": "Paper entry · ARM-FM shop machines on the freeze · 2026-11-22",
        "title": "ARM-FM shop machines end before the agent moves",
        "subtitle": f"Asked for reward machines for the shop's never-ending tasks, the ARM-FM generator made the "
        f"start state final in {len(start_final)} of {len(gated)} machines. The runtime ends an episode at a "
        "final state, so each episode ends before the first action and nothing can train. The last machine "
        "ends the episode at the first served order instead.",
        "sections": [
            {
                "id": "summary",
                "title": "In short",
                "blocks": [
                    {
                        "type": "stats",
                        "items": [
                            {
                                "value": f"{len(start_final)} of {len(gated)}",
                                "label": "gated machines whose start state is final",
                                "tone": "bad",
                            },
                            {
                                "value": f"[{low:.0%}, {high:.0%}]",
                                "label": "95% Wilson CI of that share",
                                "tone": "muted",
                            },
                            {
                                "value": f"0 of {len(gated)}",
                                "label": "machines that pass the gate",
                                "tone": "bad",
                            },
                        ],
                    },
                    {
                        "type": "list",
                        "items": [
                            '**The model wrote an accepting automaton.** Our ARM-FM prompt asks it to "declare '
                            'every accepting state" in `FINAL_STATES` '
                            '(`app/src/prompts/arm_fm/rm_generator.system.md:16`). For "whenever the siren rings, '
                            'turn it off", the state where nothing is owed accepts, and that is the start state.',
                            '**The runtime treats a final state as the end.** "Entering a final or rejecting state '
                            'ends the episode" for every RM-wrapped run (`docs/decisions/arm-fm/rm-execution.md:47`). '
                            'So the episode ends at step 0: the plan check reports "ends the episode before the agent '
                            'acts" for the solve and for every wrong plan.',
                            "**Apart from that, the simple machines are right.** All 8 siren and pot machines are "
                            "Response machines that owe a toggle or a fix after the event and pay it. It is a format "
                            "limit of ARM-FM in our runtime, not a wrong reading of the task.",
                            "**Nothing trains, so the cards count as not learned.** None of the 11 counted ARM-FM shop "
                            "cards (shop 6, shop-reward 5, same bundles) gets a run. `shop-boil` (main) finished at "
                            "21:21 after the gate; its machine starts final too (root check of `reward_machine.txt`), "
                            "so 23 of all 24 ARM-FM shop machines start final.",
                        ],
                    },
                ],
            },
            {
                "id": "machines",
                "title": "Three machines: siren, pot and serve",
                "intro": "The main bundle of each card (the card's own wording). Each starts in u0 and lists u0 as "
                "its only final state.",
                "blocks": [{"type": "details", "items": items}],
            },
            {
                "id": "boil-p3",
                "title": "The exception: shop-boil~p3 ends at the first serve",
                "intro": f"The one gated machine whose start is not final. It has {len(boil['states'])} states and "
                f"its final is {', '.join(boil['finals'])}, which every state reaches on a served order. Wrong plans "
                "that never silence the siren, never turn the stove down or leave fallen food still serve an order, "
                "so they reach the final at steps 50, 67 and 71. It passes the pay order check (finished 129.65 > "
                "not started 0) and fails the plan check.",
                "blocks": [{"type": "details", "items": [boil_item]}],
            },
            {
                "id": "all",
                "title": "All finished bundles",
                "collapsed": True,
                "intro": "Every ARM-FM shop bundle generated on the freeze that had finished, from the bundle's "
                "own machine text and status file. Paraphrase bundles (`~p1` to `~p3`) are generation records "
                "and never train.",
                "blocks": [
                    {
                        "type": "table",
                        "columns": [
                            "Bundle",
                            "Wording",
                            "States / transitions",
                            "Start / finals",
                            "Start final",
                            "Pipeline plan check",
                            "Gate",
                            "Commit",
                        ],
                        "rows": [bundle_row(m) for m in machines.values()],
                    },
                    {
                        "type": "text",
                        "text": f"Generation commits run from `{commits[0]}` to `{commits[-1]}` on main (main moved "
                        "while the background generation ran; all are after the freeze `809dfe3`). In `app/` only "
                        "the box-carry half fall world (`507886e`, merged as `e37dff9`) and the tagger default "
                        "(`f634e0f`) changed in that span; neither touches the machine generator.",
                    },
                ],
            },
            {
                "id": "limits",
                "title": "Limits",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "`shop-boil` (main) finished after the gate (21:21). Its plan check reports a final start and its "
                            "machine has INITIAL_STATE u0 = FINAL_STATES u0 (root check), so the two counted "
                            "`shop-boil` cards count as not learned.",
                            "`shop-boil~p2` finished after the gate. Its own pipeline plan check reports a final "
                            "start too, but it was not gated, so it is listed and not counted.",
                            "The extra findings per machine (the soft fall rule on `shop-serve`) are the gate "
                            "agent's read of the machine text, not a run.",
                            "One generation per wording, at reasoning max with deepseek-v4.1-flash and the "
                            "glm-5.3-flash critic; other models or prompts were not tried.",
                        ],
                    }
                ],
            },
            {
                "id": "files",
                "title": "Files and rerun",
                "collapsed": True,
                "blocks": [
                    {
                        "type": "code",
                        "text": "# from the repository root, inside RM_RL_env (no model call)\n"
                        "PYTHONPATH=app python -W ignore docs/paper/armfm-shop-start-final/check/build_page.py\n"
                        "python3 <agent-artifacts skill>/scripts/fill.py docs/paper/armfm-shop-start-final/data.json "
                        "docs/paper/armfm-shop-start-final/index.html\n"
                        "# the plan check again on the copies, unpacked in a scratch folder W (writes "
                        "W/bundles-freeze/arm-fm/<name>.plan_check.json)\n"
                        "tar -xzf docs/paper/armfm-shop-start-final/evidence/bundles-freeze.tar.gz -C W\n"
                        "PYTHONPATH=app python -W ignore app/main.py check-plans --tasks experiments/benchmark/shop/"
                        "tasks.json --bundles W/bundles-freeze\n"
                        "# the machine graphs\n"
                        "PYTHONPATH=app python app/main.py render-rm --rm-file docs/paper/armfm-shop-start-final/"
                        "graphs/shop-siren.rm --svg-dir docs/paper/armfm-shop-start-final/graphs/shop-siren.svg --html",
                    }
                ],
            },
        ],
    }


if __name__ == "__main__":
    (ENTRY / "data.json").write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print("wrote", ENTRY / "data.json")
