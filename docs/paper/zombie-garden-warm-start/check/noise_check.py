"""Diagnosis check: do side trips still pay when the policy is noisy, as PPO's sampled policy is?

Each scripted policy takes a uniformly random action (of the 7) with probability EPS, else its own.
EPS 0.15-0.2 is about PPO's late entropy (0.5-0.9 nats over 7 actions).
Usage (repository root): PYTHONPATH=app:<this folder> python noise_check.py [--n 100] [--procs 6]
"""

import argparse
from functools import partial
from multiprocessing import Pool

import gymnasium as gym
import numpy as np
import policies

from src.arm_fm import forcing_envs as fe

EPS = (0.0, 0.05, 0.1, 0.2, 0.3)
NAMES = ("top_only", "gp8m", "gp8", "guard")


def episode(job):
    name, eps, seed = job
    env = gym.make(fe.LANES_ID)
    env.reset(seed=seed)
    base = env.unwrapped
    rng = np.random.default_rng(seed + 7)
    policy = policies.BASES[name]
    ret = disc_ret = 0.0
    disc = 1.0
    side = plants = 0
    top_held = True
    while True:
        action = int(rng.integers(7)) if rng.random() < eps else policy(base)
        _, _, term, trunc, info = env.step(action)
        side += info["events"].count("side_breach")
        plants += info["events"].count("plant_trampled")
        r, rejected = policies.machine_reward(info["events"])
        ret += r
        disc_ret += disc * r
        disc *= policies.GAMMA
        if rejected:
            top_held = False
            break
        if term or trunc:
            break
    env.close()
    return name, eps, top_held, side, plants, ret, disc_ret


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--procs", type=int, default=6)
    a = p.parse_args()
    jobs = [(n, e, s) for n in NAMES for e in EPS for s in list(policies.SEEDS)[: a.n]]
    with Pool(a.procs) as pool:
        rows = pool.map(episode, jobs, chunksize=10)
    for e in EPS:
        for n in NAMES:
            sel = [r for r in rows if r[0] == n and r[1] == e]
            m = partial(policies.mean_of, sel)
            print(
                f"eps {e:.2f} {n:9s} top_held {m(2):.2f} side {m(3):5.2f} plants {m(4):.2f} "
                f"RM {m(5):7.2f} disc {m(6):6.2f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
