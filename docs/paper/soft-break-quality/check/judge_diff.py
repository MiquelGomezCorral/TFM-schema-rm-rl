"""Compare a new judge.json with an old one: fields that differ, and fields only the new one has.

Usage: python judge_diff.py NEW_JUDGE OLD_JUDGE
Top-level fields and every per-episode field are compared; ``rm_bundle`` and paths are compared
as text, so a copied run that points at the same bundle matches.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    new, old = (json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:3])
    differ = [key for key in old if key != "per_episode" and new.get(key) != old[key]]
    added = [key for key in new if key not in old]
    episode_differ, episode_added = set(), set()
    for new_episode, old_episode in zip(new["per_episode"], old["per_episode"], strict=True):
        episode_differ |= {key for key in old_episode if new_episode.get(key) != old_episode[key]}
        episode_added |= {key for key in new_episode if key not in old_episode}
    print(f"episodes: {len(new['per_episode'])}")
    print(f"top-level fields that differ: {differ or 'none'}")
    print(f"top-level fields only in the new one: {added or 'none'}")
    print(f"per-episode fields that differ: {sorted(episode_differ) or 'none'}")
    print(f"per-episode fields only in the new one: {sorted(episode_added) or 'none'}")
    for key in ("mean_judged_success", "mean_success", "mean_soft_breaks"):
        if key in old or key in new:
            print(f"{key}: old {old.get(key)} new {new.get(key)}")


if __name__ == "__main__":
    main()
