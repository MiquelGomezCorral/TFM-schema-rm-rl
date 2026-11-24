"""Build ``data.json`` of the shop-net-zero-pay entry from its evidence copies.

Every number on the page comes from ``evidence/``: the replay of four plans on the judge's seeds
(``evidence/shop-pricing/<bundle>.json``, written by ``check/shop_pricing.py play``), the ladder's
own check on reset seeds 1-20 (``evidence/pricing-check.json``, ``check/pricing_check.py``) and the
judge files of the 51 trained shop runs (``evidence/judge/``). Clauses and tasks come from the shop
cards, machine sizes from the committed bundles.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/shop-net-zero-pay/check/build_page.py
"""

import json
import math
from pathlib import Path
from statistics import fmean

from src.benchmark import load_cards
from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
CARDS = ROOT / "experiments/benchmark/shop/tasks.json"
FARM = ROOT / "experiments/benchmark/shop/bundles/farm"
COUNTED = ("shop-siren", "shop-serve", "shop-full", "shop-quiet-first", "shop-boil", "shop-pot")
LADDER = (
    "shop-ladder-deliver",
    "shop-ladder-deliver-siren",
    "shop-ladder-order-deliver",
    "shop-ladder-order-deliver-siren",
)
DRAWN = {"shop-siren", "shop-pot", "shop-serve", *LADDER[:3]}  # the rest are 0.1 to 2.4 MB of text
PLANS = (
    ("idle", "Idle"),
    ("order-stop", "Take one order, stop"),
    ("serve-stop", "Serve one, stop"),
)
Z95 = 1.959964


def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def number(value: float) -> str:
    return f"{round(value, 2) + 0.0:.2f}"  # + 0.0 turns -0.0 into 0.0


def returns(episodes: list[dict]) -> str:
    plain = fmean(e["plain"] for e in episodes)
    disc = fmean(e["disc_shop"] for e in episodes)
    return f"{number(plain)} / {number(disc)}"


def replay(name: str, variant: str) -> dict:
    return json.loads((ENTRY / "evidence/shop-pricing" / f"{name}.json").read_text())[variant]


def solve_margin(name: str, variant: str, key: str) -> float:
    """How much the solve beats the best stop plan; a stop plan that never stopped is the solve itself."""
    plans = replay(name, variant)
    solve = fmean(e[key] for e in plans["solve"])
    others = [
        fmean(e[key] for e in plans[plan]) for plan, _ in PLANS if plans[plan] != plans["solve"]
    ]
    return solve - max(others)


def margin_range(variant: str, key: str) -> str:
    margins = [solve_margin(name, variant, key) for name in (*COUNTED, *LADDER)]
    assert min(margins) > 0, (variant, key, "a stop plan beats the solve")
    return f"{min(margins):.2f} to {max(margins):.2f}"


def replay_rows(variant: str) -> list[list]:
    rows = []
    for name in (*COUNTED, *LADDER):
        plans = replay(name, variant)
        solve = plans["solve"]
        pays = [pay for episode in solve for pay in episode["order_pays"]]
        per_order = f"{number(fmean(pays))} ({min(pays):.0f} to {max(pays):.0f})" if pays else "-"
        rows.append(
            [
                f"`{name}`",
                *(returns(plans[key]) for key, _ in PLANS),
                {"text": returns(solve), "tone": "ok" if variant == "off" else "info"},
                f"{fmean(e['served'] for e in solve):.2f}",
                per_order,
            ]
        )
        if variant == "off":
            assert all(e["plain"] == 0.0 for e in solve), (name, "the solve no longer nets 0")
    return rows


def ladder_rows() -> list[list]:
    check = json.loads((ENTRY / "evidence/pricing-check.json").read_text())
    rows = []
    for name, row in check.items():
        if "~" in name:
            continue
        rows.append(
            [
                f"`{name}`",
                f"{row['solve']['served']:.2f}",
                f"{row['solve']['plain']:.2f} / {row['solve']['discounted']:.2f}",
                f"{row['one']['plain']:.2f} / {row['one']['discounted']:.2f}",
                f"{row['idle']['plain']:.2f} / {row['idle']['discounted']:.2f}",
                f"{row['pay_per_extra_order']['plain']:.2f} / {row['pay_per_extra_order']['discounted']:.2f}",
            ]
        )
    return rows


def agent_runs() -> tuple[list[list], int, int]:
    rows, runs, serving = [], 0, 0
    for folder in sorted((ENTRY / "evidence/judge").iterdir()):
        _, suite, card, arm, _ = folder.name.split("__")
        judges = [json.loads((run / "judge.json").read_text()) for run in sorted(folder.iterdir())]
        runs += len(judges)
        serving += sum(judge["mean_served_success"] > 0 for judge in judges)
        rows.append(
            [
                suite,
                f"`{card}`",
                "FARM + world reward"
                if suite == "shop-reward"
                else {"farm": "FARM", "no-rm": "no-RM"}[arm],
                ", ".join(f"{judge['mean_served_count']:.2f}" for judge in judges),
                ", ".join(f"{judge['mean_judged_success']:.2f}" for judge in judges),
            ]
        )
    return rows, runs, serving


def machine_size(name: str) -> tuple[int, int, str]:
    text = (FARM / name / "reward_machine.txt").read_text()
    states = next(line for line in text.splitlines() if line.startswith("STATES:"))
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    return len(states.split(",")), sum(line.startswith("(") for line in body.splitlines()), text


def machine_item(card) -> dict:
    manifest = json.loads((FARM / card.id / "manifest.json").read_text())
    stored = sorted(json.dumps(clause) for clause in manifest["generation"]["clauses"])
    assert stored == sorted(json.dumps([t, list(names), p]) for t, names, p in card.expect), card.id
    states, transitions, text = machine_size(card.id)
    clauses = [
        [f"{t}({', '.join(names)}) {priority}", f"`{pretty_ltlf(ltlf_of(t, list(names)))}`"]
        for t, names, priority in card.expect
    ]
    blocks = [
        {"type": "text", "text": f"**Task:** {card.task}"},
        {
            "type": "table",
            "columns": ["Clause (card answer = stored clauses)", "LTLf"],
            "rows": clauses,
        },
    ]
    if card.id in DRAWN:
        blocks += [
            {
                "type": "figure",
                "src": f"graphs/{card.id}.html",
                "height": 520,
                "caption": f"The FARM machine the runs trained on: {states} states, {transitions} transitions, "
                "no final state. Drag a state, click an edge for its cases.",
            },
            {
                "type": "details",
                "items": [{"title": "RM text", "blocks": [{"type": "code", "text": text}]}],
            },
        ]
    else:
        blocks.append(
            {
                "type": "text",
                "text": f"The machine has {states} states and {transitions} transitions ({len(text) / 1e6:.1f} MB "
                f"of text), too big to draw or fold out here. It is `experiments/benchmark/shop/bundles/farm/"
                f"{card.id}/reward_machine.txt` at main `881b22d`.",
            }
        )
    role = "held-out ladder rung" if card.id in LADDER else "counted card"
    return {"title": f"{card.id} ({role})", "preview": f"{states} states", "blocks": blocks}


def build() -> dict:
    cards = {card.id: card for card in load_cards(CARDS).cards}
    agent_rows, runs, serving = agent_runs()
    low, high = wilson(serving, runs)
    serve_pays = [
        pay for episode in replay("shop-serve", "off")["solve"] for pay in episode["order_pays"]
    ]
    assert set(serve_pays) == {0.0}, "a shop-serve order no longer nets 0"
    replay_columns = [
        "Machine",
        *(label for _, label in PLANS),
        "Solve",
        "Served by the solve",
        "Pay per served order (min to max)",
    ]
    return {
        "eyebrow": "Paper entry · FARM shop machines · 2026-11-22",
        "title": "Shop machines pay nothing per order",
        "subtitle": "A FARM shop machine gives back every charge it makes, so serving one client or seventeen "
        "earns the same. Only what is still open at the end of the shift counts. The agents' failure to serve "
        "has another cause: no arm, not even one paid by the world for each serve, ever serves an order.",
        "sections": [
            {
                "id": "summary",
                "title": "In short",
                "blocks": [
                    {
                        "type": "callout",
                        "tone": "info",
                        "title": "About 0 per served order: exactly 0 on 3 of the 10 shop machines",
                        "text": f"On `shop-serve` every one of the {len(serve_pays)} orders the scripted worker "
                        "served on the judge's 100 test seeds netted exactly 0, as on the 2 ladder machines without a "
                        "siren. On the other 7 machines a served order pays +1 or -1 on 2.2% to 7.1% of orders (siren "
                        "pay falling between serves), a mean of -0.003 to -0.010. A client arriving costs 3, and taking "
                        "the order, cooking "
                        "and serving pay 1 each back. So the episode return only counts what is still open at the "
                        "end: solve 0, take one order and stop -2, idle -3, serve one order and stop -3.",
                    },
                    {
                        "type": "list",
                        "items": [
                            "**The machines rank the plans right, by little.** The solve is the best plan on every "
                            f"machine, but only by {margin_range('off', 'disc_shop')} per episode discounted "
                            f"({solve_margin('shop-serve', 'off', 'disc_shop'):.2f} on `shop-serve`), and serving "
                            "more orders does not raise it.",
                            "**It is the pricing rule, not a bug and not the model.** All 10 clause sets equal the "
                            "card's answer. A machine with a net-positive loop is refused at build time, and the end "
                            "charge for an order left open is off by default since commit `deff802`.",
                            f"**Pricing is not why the agents serve 0.** {serving} of {runs} trained shop runs "
                            f"served any order in their 100 test episodes ({serving / runs:.0%}, 95% CI "
                            f"[{low:.0%}, {high:.1%}]), no-RM and FARM with the world's +1 per serve included. On the "
                            "six counted cards serving needs cooking, and no arm gets that far: an exploration "
                            "limit of every arm.",
                            "**What made the shop learn before was an end cost.** Every shop run that learned had an "
                            "open promise that cost something as the step limit ran out: 12 of 12 seeds served, "
                            "against 0 of 12 with both costs off (see [Shop promise cost]"
                            "(../shop-promise-cost/index.html)). Even with that cost on, `shop-serve` learned 0 of "
                            "3: random play never prepared food in 1,000 episodes.",
                        ],
                    },
                ],
            },
            {
                "id": "plans",
                "title": "What each plan earns",
                "intro": "The machine's return per episode for four scripted plans, played on the judge's test seeds "
                "2000000 to 2000099 (100 episodes per plan) and replayed through the stored FARM bundle. Plain sum, "
                "then discounted at 0.995 (the shop runs' PPO gamma). Episodes are cut at the well, with the "
                "time-limit penalty 0 and the end judgment off, as in the runs.",
                "blocks": [
                    {
                        "type": "table",
                        "heading": "Return per episode, plain / discounted (judge seeds, 100 per plan)",
                        "columns": replay_columns,
                        "rows": replay_rows("off"),
                    },
                    {
                        "type": "text",
                        "text": "**Take one order, stop** runs the scripted worker until the first order is taken, "
                        "then does nothing. **Serve one, stop** runs it until the first serve. **Pay per served "
                        "order** sums the machine's pay from the step after one serve to the next serve, over every "
                        "order the solve served; the -1 to +1 spread is a siren or a boiling pot charged or paid "
                        "back between two serves. On the ladder's first two rungs no order is taken, so \"take one "
                        'order, stop" plays the whole solve.',
                    },
                    {
                        "type": "text",
                        "text": "Serving one order and stopping pays less than taking one order and stopping (-3 "
                        "against -2 on `shop-serve`): the serve brings the next client, and that client's -3 is never "
                        "paid back. The trained FARM agents' RM return of -2.00 on serve, full, quiet-first and boil "
                        "(table below) is exactly this local optimum.",
                    },
                    {
                        "type": "table",
                        "heading": "The ladder's own check: each rung's world, reset seeds 1 to 20",
                        "columns": [
                            "Machine",
                            "Served by the solve",
                            "Solve, plain / discounted",
                            "Serve one then stop",
                            "Idle",
                            "Pay per extra order, plain / discounted",
                        ],
                        "rows": ladder_rows(),
                    },
                    {
                        "type": "text",
                        "text": "The four ladder rungs (held out, `train: false`) and, as rung 5, `shop-serve`'s "
                        'machine in the siren-off world. "Serve one then stop" keeps answering the siren and the '
                        'food slips after its serve. "Pay per extra order" is the solve\'s gain over serving one, '
                        "divided by the extra orders: 0.04 to 0.18 discounted, so a twelfth order is worth almost "
                        "nothing. Other seeds and slightly other plans than the table above, so the numbers differ "
                        "a little.",
                    },
                ],
            },
            {
                "id": "cause",
                "title": "Why: the pricing rule works as designed",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "**No final state, so no completion pay.** The +10 is paid only on an edge into a final "
                            "state (`app/src/compiler/reward_layer.py:643-646`); the shop machines have none.",
                            "**Progress is a potential over the stages still owed.** Without a final it aims at the "
                            "states where nothing is pending (`reward_layer.py:763`, `:772`). The chain weights "
                            "(`reward_layer.py:399-420`) give `Response(client_arrived, order_taken)` weight 3, since "
                            "it hands off to the order and cooking rules. So an arrival charges -3 and order, cooking "
                            "and serve pay back +1 each: every loop sums to 0.",
                            "**A positive loop is refused at build** (`reward_layer.py:183`). Record: "
                            '`docs/decisions/arm-fm/rm-execution.md:233-236` ("It stays a potential, so no loop '
                            'gains").',
                            "**Nothing charges an order still open at the end.** The end judgment is off by default "
                            "(`app/src/config/config.py:269-271`, commit `deff802`), and benchmark runs set "
                            "`time_limit_penalty: 0.0` (`app/src/benchmark/traces.py:39-42`), so the runtime adds "
                            "nothing at the time limit (`app/src/arm_fm/runtime.py:222-226`).",
                            "**The world turns a serve into a new charge.** The next client comes a gap after the "
                            "previous one is served (`app/src/arm_fm/shop.py:88-91`).",
                            "**Discounting adds only a small push.** The pay is undiscounted and the learner is not, "
                            "so each step with stages open costs about (1 - gamma) times the stages owed. The switch "
                            'to discounted shaping was left "to decide after the shop runs" '
                            "(`docs/COMPILER_REWARD_DESIGN.md:154-163`, `rm-execution.md:271-273`).",
                        ],
                    },
                    {
                        "type": "callout",
                        "tone": "muted",
                        "title": "A right machine for these tasks should not pay per order",
                        "text": "In LTLf, `G(client_arrived -> F order_taken)` counts no orders: it holds on a finite "
                        "trace when no arrival is left without its answer, so serving 1 or 17 clients is equally "
                        "correct. Throughput comes from the world, not from the instruction. What a machine should do "
                        "is price an order left open, which the end judgment or the promise cost does (both existing "
                        "switches, both off in the final run).",
                    },
                ],
            },
            {
                "id": "agents",
                "title": "No arm serves on the six counted cards",
                "intro": "The judge's greedy test of every trained shop run: orders served per episode and the share "
                "of episodes judged a success, one number per seed. ARM-FM trained none of these cards: its "
                "machines end the episode before the agent acts (see [ARM-FM shop machines]"
                "(../armfm-shop-start-final/index.html)).",
                "blocks": [
                    {
                        "type": "stats",
                        "items": [
                            {
                                "value": f"{serving} of {runs}",
                                "label": "trained runs that served any order",
                                "tone": "bad",
                            },
                            {
                                "value": f"[{low:.0%}, {high:.1%}]",
                                "label": "95% Wilson CI of that share",
                                "tone": "muted",
                            },
                            {
                                "value": "+1",
                                "label": "world pay per serve that no-RM and FARM + world reward get",
                                "tone": "info",
                            },
                        ],
                    },
                    {
                        "type": "table",
                        "columns": [
                            "Suite",
                            "Card",
                            "Arm",
                            "Served per episode (seeds 1, 2, 3)",
                            "Judged (seeds 1, 2, 3)",
                        ],
                        "rows": agent_rows,
                    },
                    {
                        "type": "text",
                        "text": "On the two instructions that never mention clients the judge passes FARM on "
                        "`shop-siren` (3 of 3 seeds) and `shop-pot` (2 of 3), and no-RM on `shop-pot` (3 of 3), "
                        "with no order served. These instructions never ask for serving, and a run is learned from "
                        "its judged success alone, so these runs count as learned. `shop-reward` is FARM on the same bundles with `reward_source: both`; its no-RM runs were not "
                        "in the source table and are left out here.",
                    },
                ],
            },
            {
                "id": "promise-cost",
                "title": "With the promise cost on (replay only, nothing trained)",
                "collapsed": True,
                "intro": "The same plans replayed through copies rebuilt with `rebuild-rewards --promise-cost` (no "
                "model call). Each order now costs the time it stays open, so serving faster pays more and the solve "
                f"wins by {margin_range('pc', 'plain')} plain. Turning it on changes the FARM method after the "
                "freeze, and `shop-serve` trained with it on still learned 0 of 3 (Shop promise cost).",
                "blocks": [
                    {
                        "type": "table",
                        "heading": "Return per episode with the promise cost, plain / discounted (judge seeds)",
                        "columns": replay_columns,
                        "rows": replay_rows("pc"),
                    }
                ],
            },
            {
                "id": "machines",
                "title": "The ten machines: task, LTLf and RM",
                "collapsed": True,
                "intro": "Each machine's task and clauses (all equal to the card's answer), with the live graph and "
                "RM text for the six machines small enough to draw.",
                "blocks": [
                    {
                        "type": "details",
                        "items": [machine_item(cards[name]) for name in (*COUNTED, *LADDER)],
                    }
                ],
            },
            {
                "id": "limits",
                "title": "Limits",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "The replay pays scripted plans, not the trained agents; the agents' own numbers are the "
                            "judge table.",
                            "`shop-boil`: the commit `881b22d` holds a failed generation; the worktree bundle is "
                            "uncommitted, marked `reconstructed`, and its manifest, labeling and texts were rewritten "
                            "the evening of 2026-11-22. Its machine predates the runs and its clauses equal the card's, "
                            "but no hash proves the replayed labeling is the one the runs used.",
                            "The end judgment option was not replayed: no rebuild tool turns it on without a compile.",
                            "The paraphrase bundles (`~p1` to `~p3`) are generation checks and were not replayed.",
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
                        "text": "# from the repository root, inside RM_RL_env (no model call, no training)\n"
                        "PYTHONPATH=app python -W ignore docs/paper/shop-net-zero-pay/check/build_page.py\n"
                        "python3 <agent-artifacts skill>/scripts/fill.py docs/paper/shop-net-zero-pay/data.json "
                        "docs/paper/shop-net-zero-pay/index.html\n"
                        "# the replay table from the copies (judge rows from evidence/judge/)\n"
                        "PYTHONPATH=app python -P -W ignore docs/paper/shop-net-zero-pay/check/shop_pricing.py table\n"
                        "# the replay itself, about 5 min per bundle; first rebuild the promise-cost copy:\n"
                        "PYTHONPATH=app python app/main.py rebuild-rewards --bundle experiments/benchmark/shop/"
                        "bundles/farm/<bundle> --output docs/paper/shop-net-zero-pay/evidence/shop-pricing/bundles/"
                        "<bundle>-pc --promise-cost --gym-id MiniGrid-Shop-v0 --env-kwargs '<card env_kwargs>'\n"
                        "PYTHONPATH=app OMP_NUM_THREADS=2 python -P -W ignore docs/paper/shop-net-zero-pay/check/"
                        "shop_pricing.py play <bundle>\n"
                        "# the ladder check\n"
                        "PYTHONPATH=app python -W ignore docs/paper/shop-net-zero-pay/check/pricing_check.py --out "
                        "<json> --seeds 20 shop-ladder-deliver@experiments/benchmark/shop/bundles/farm/"
                        "shop-ladder-deliver ...",
                    }
                ],
            },
        ],
    }


if __name__ == "__main__":
    (ENTRY / "data.json").write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print("wrote", ENTRY / "data.json")
