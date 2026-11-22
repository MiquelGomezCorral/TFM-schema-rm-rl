"""Run `check-pay-order` (one process at a time) on every copy of a set/suite folder; save the outputs.

Usage (cwd = the main checkout, PYTHONPATH=app): python pay_order.py SUITE COPIES_DIR OUT_JSON
The card is the copy name before `~`; its gym id and env kwargs set the step limit, as the gate does.
"""

import json
import subprocess
import sys
from pathlib import Path

from src.benchmark.cards import load_cards


def main() -> None:
    suite, copies, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    cards = {
        c.id: c for c in load_cards(Path("experiments/benchmark") / suite / "tasks.json").cards
    }
    results = {}
    for folder in sorted(p for p in copies.glob("*/*") if (p / "manifest.json").is_file()):
        card = cards[folder.name.split("~", 1)[0]]
        argv = [
            sys.executable,
            "app/main.py",
            "check-pay-order",
            str(folder),
            "--gym-id",
            card.env["gym_id"],
            "--env-kwargs",
            json.dumps(card.env.get("env_kwargs") or {}),
        ]
        run = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603  fixed argv, no shell
        text = (run.stdout + run.stderr).strip()
        ok = (
            run.returncode == 0
            and "; ok" in text
            and "broken" not in text
            and "not checked" not in text
        )
        results[f"{folder.parent.name}/{folder.name}"] = {"ok": ok, "output": text}
        print(f"{folder.parent.name}/{folder.name}: {'ok' if ok else 'NOT ok'}")
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
