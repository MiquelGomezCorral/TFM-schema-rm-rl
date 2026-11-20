"""Step 1: scripted policies on MiniGrid-Lanes-v0, scored with the lanes-rules machine.

Machine (bundle lanes-rules): top breach -> rejecting u1, reward -96.0959, episode ends;
each side breach or trampled plant -1 and stay in u0. Test seeds 2000000..2000099.

Policies (what they see):
- idle: nothing.
- top_only: the full grid; walks to top-lane zombies only (forcing_envs route, avoids plants).
- guard: forcing_envs.scripted_policy (top-first, then nearest side zombie).
- urgency: the full grid plus each zombie's walking phase (inferable from two frames).
  Picks the zombie whose breach is nearest in time among those it can still reach, but
  never lets a top-lane zombie go if a side detour would cost it; waits at a central post.
- rollout: urgency + one-step lookahead: tries each action, then plays `urgency` for H steps
  on copies of the env whose FUTURE spawns are redrawn from the known spawn law (so it uses
  no knowledge of the seed's future), K copies; picks the best mean machine return.
  With --oracle it keeps the true future instead (full-knowledge oracle).
"""

import argparse
import copy
import json
import sys
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import gymnasium as gym
import numpy as np
from minigrid.core.actions import Actions

from src.arm_fm import forcing_envs as fe  # registers the ids

TOP_COST, SOFT_COST = -96.0959, -1.0
GAMMA = 0.99
SEEDS = range(2000000, 2000100)


def machine_reward(events):
    """Return (reward, rejected) for one step of the lanes-rules machine in u0."""
    if "top_breach" in events:
        return TOP_COST, True
    return SOFT_COST * (events.count("side_breach") + events.count("plant_trampled")), False


def mean_of(rows, key):
    """Mean of `row[key]` over rows (dicts or tuples)."""
    return np.mean([r[key] for r in rows])


# ---------------------------------------------------------------- policies
def idle(_base):
    return int(Actions.done)


def top_only(base):
    tops = sorted(
        (tuple(z.cur_pos) for z in base.zombies if z.cur_pos[1] == fe.LANE_ROWS[0]),
        key=lambda c: c[0],
    )
    action = fe._step_toward(base, tops, in_order=True)
    return int(Actions.done) if action is None else action


def guard(base):
    return fe.scripted_policy(base)


def _breach_time(base, z):
    """Env steps until zombie z breaches (it moves when (t - born) % 3 == 0)."""
    t = base.step_count
    # steps until its next move: smallest k>=1 with (t + k - born) % 3 == 0
    k = (-(t - z.born)) % fe.ZOMBIE_PERIOD or fe.ZOMBIE_PERIOD
    x = z.cur_pos[0]  # it needs x moves to breach (x-1 to reach column 1, then one more)
    return k + (x - 1) * fe.ZOMBIE_PERIOD


POST = (3, 5)  # waiting post: left of centre on the middle lane


def urgency(base):
    zs = list(base.zombies)
    if not zs:
        route = fe._route(base, lambda x, y, _d: (x, y) == POST)
        return int(Actions.done) if not route else int(route[0])
    cand = []
    for z in zs:
        route = fe._route(base, fe._faces(tuple(z.cur_pos)))
        if route is None:
            continue
        reach = len(route) + 1  # +1 forward onto it (approx; it moves meanwhile)
        bt = _breach_time(base, z)
        top = z.cur_pos[1] == fe.LANE_ROWS[0]
        cand.append((z, route, reach, bt, top))
    if not cand:
        return int(Actions.done)
    tops = [c for c in cand if c[4]]
    # most urgent top zombie
    if tops:
        t0 = min(tops, key=lambda c: c[3])
        slack = t0[3] - t0[2]
        # a side zombie detour is allowed only if it is urgent, close, and leaves top slack
        sides = [c for c in cand if not c[4] and c[3] - c[2] >= -2]
        best = None
        for c in sorted(sides, key=lambda c: c[2]):
            # rough: go to side (reach), then to the top zombie: |dy| + |dx| + turns ~ 4..12
            dy = abs(c[0].cur_pos[1] - t0[0].cur_pos[1])
            dx = abs(c[0].cur_pos[0] - t0[0].cur_pos[0])
            back = dy + max(0, dx - (c[2] + dy) // 3) + 3
            if c[2] + back < t0[3] - 2 and c[2] <= 6:
                best = c
                break
        if best is None or slack < 0:
            return _first(t0[1])
        return _first(best[1])
    # no top zombie: most urgent reachable side zombie, else nearest
    alive = [c for c in cand if c[3] - c[2] >= -1]
    pick = min(alive, key=lambda c: c[3]) if alive else min(cand, key=lambda c: c[2])
    return _first(pick[1])


def _first(route):
    return int(route[0] if route else Actions.forward)


def make_guardp(max_side, lanes, post):
    def policy(base):
        zs = sorted((tuple(z.cur_pos) for z in base.zombies), key=lambda c: c[0])
        tops = [c for c in zs if c[1] == fe.LANE_ROWS[0]]
        a = fe._step_toward(base, tops, in_order=True)
        if a is not None:
            return a
        routes = []
        for c in zs:
            if c[1] in lanes:
                r = fe._route(base, fe._faces(c))
                if r is not None and len(r) <= max_side:
                    routes.append(r)
        if routes:
            return _first(min(routes, key=len))
        if post is not None and tuple(base.agent_pos) != post and base.grid.get(*post) is None:
            r = fe._route(base, lambda x, y, _d: (x, y) == post)
            if r:
                return int(r[0])
        return int(Actions.done)

    return policy


for _L in (3, 5, 8, 12, 99):
    for _post in (None, (3, 3), (5, 3)):
        _n = f"gp{_L}" + ("" if _post is None else f"p{_post[0]}{_post[1]}")
        globals()[_n] = make_guardp(_L, (5, 9), _post)
        globals()[_n + "m"] = make_guardp(_L, (5,), _post)

BASES = {"idle": idle, "top_only": top_only, "guard": guard, "urgency": urgency}
BASES.update({k: v for k, v in list(globals().items()) if k.startswith("gp")})


# ---------------------------------------------------------------- rollout planner
def _redraw_future(sim, rng):
    t = sim.step_count
    steps = sim.max_steps
    chance = np.linspace(*fe.SPAWN_CHANCE, steps)
    sim._spawns = sim._spawns.copy()
    sim._spawn_lanes = sim._spawn_lanes.copy()
    sim._spawns[t:] = rng.random(steps - t) < chance[t:]
    sim._spawn_lanes[t:] = rng.integers(0, 3, size=steps - t)


def _sim_return(sim, first_action, base_policy, horizon, gamma):
    total, disc = 0.0, 1.0
    action = first_action
    for _ in range(horizon):
        _, _, term, trunc, info = sim.step(action)
        r, rejected = machine_reward(info["events"])
        total += disc * r
        disc *= gamma
        if rejected or term or trunc:
            break
        action = base_policy(sim)
    return total


def make_rollout(base_policy, horizon, k, oracle, seed):
    rng = np.random.default_rng(seed)
    actions = (int(Actions.left), int(Actions.right), int(Actions.forward), int(Actions.done))

    def policy(base):
        scores = []
        for a in actions:
            s = 0.0
            for _ in range(1 if oracle else k):
                sim = copy.deepcopy(base)
                if not oracle:
                    _redraw_future(sim, rng)
                s += _sim_return(sim, a, base_policy, horizon, GAMMA)
            scores.append(s / (1 if oracle else k))
        return actions[int(np.argmax(scores))]

    return policy


# ---------------------------------------------------------------- evaluation
def run_episode(args):
    name, seed, opts = args
    env = gym.make(fe.LANES_ID)
    env.reset(seed=seed)
    base = env.unwrapped
    if name.startswith("rollout"):
        policy = make_rollout(BASES[opts["base"]], opts["h"], opts["k"], opts["oracle"], seed)
    else:
        policy = BASES[name]
    ret = disc_ret = 0.0
    disc = 1.0
    length = 0
    counts = dict.fromkeys(("side_breach", "plant_trampled", "zombie_killed"), 0)
    top_held = True
    while True:
        action = policy(base)
        _, _, term, trunc, info = env.step(action)
        length += 1
        for e in counts:
            counts[e] += info["events"].count(e)
        r, rejected = machine_reward(info["events"])
        ret += r
        disc_ret += disc * r
        disc *= GAMMA
        if rejected:
            top_held = False
            break
        if term or trunc:
            break
    env.close()
    return {
        "seed": seed,
        "top_held": top_held,
        "len": length,
        "ret": ret,
        "disc": disc_ret,
        **counts,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("policies", nargs="+")
    p.add_argument("--h", type=int, default=30)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--base", default="urgency")
    p.add_argument("--oracle", action="store_true")
    p.add_argument("--procs", type=int, default=8)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    opts = {"h": a.h, "k": a.k, "base": a.base, "oracle": a.oracle}
    rows_all = {}
    for name in a.policies:
        jobs = [(name, s, opts) for s in list(SEEDS)[: a.n]]
        with Pool(a.procs) as pool:
            rows = pool.map(run_episode, jobs)
        rows_all[name] = rows
        m = partial(mean_of, rows)
        print(
            f"{name:10s} top_held {m('top_held'):.2f} side {m('side_breach'):.2f} plants "
            f"{m('plant_trampled'):.2f} kills {m('zombie_killed'):.1f} len {m('len'):.0f} "
            f"RM {m('ret'):.2f} disc {m('disc'):.2f}",
            flush=True,
        )
    if a.out:
        Path(a.out).write_text(json.dumps(rows_all))


if __name__ == "__main__":
    sys.exit(main())
