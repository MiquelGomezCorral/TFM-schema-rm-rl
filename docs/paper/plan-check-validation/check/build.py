"""Build the study's bundle copies under S/copies/<set>/<suite>/<arm>/<name>/ from spec.json.

Sources never change: stored bundles and archives are copied, git versions come from read-only
`git show`, level-benchmark runs are put into a copy of their card's final bundle, and mutants edit
their copy only. Usage (cwd = the main checkout): python build.py S_DIR
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

BENCH = Path("experiments/benchmark")
LEVEL_BENCH = Path("docs/paper/level-benchmark-freeze/records/none")
SKIP = {"embeddings.json", "raw_responses.json", "attempts.json"}  # not read by the checks
GIT = shutil.which("git") or "/usr/bin/git"  # a full path, so no call depends on a PATH lookup


def copy_folder(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=lambda _dir, names: [n for n in names if n in SKIP])


def copy_from_git(commit: str, folder: str, target: Path) -> None:
    listing = subprocess.run(  # noqa: S603  fixed argv, no shell
        [GIT, "ls-tree", "-r", "--name-only", commit, folder + "/"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    if not listing:
        raise SystemExit(f"{commit}:{folder} has no files")
    for path in listing:
        name = Path(path).name
        if name in SKIP:
            continue
        blob = subprocess.run(  # noqa: S603  fixed argv, no shell
            [GIT, "show", f"{commit}:{path}"], check=True, capture_output=True
        ).stdout
        (target / Path(path).relative_to(folder)).parent.mkdir(parents=True, exist_ok=True)
        (target / Path(path).relative_to(folder)).write_bytes(blob)


def put_level_bench_run(run: str, target: Path) -> None:
    """Replace the copy's machine and clauses with the level-benchmark run's."""
    record = json.loads((LEVEL_BENCH / f"{run}.json").read_text(encoding="utf-8"))
    (target / "reward_machine.txt").write_text(record["machine"], encoding="utf-8")
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generation"].update(
        clauses=record["clauses"], clause_texts=record["texts"], compiler_text=record["machine"]
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def set_function_body(text: str, name: str, body: str) -> str:
    """Replace the one-line body of labeling function ``name``."""
    pattern = rf"(def {name}\(env\):\n)    return .*\n"
    new, count = re.subn(pattern, lambda m: m.group(1) + f"    return {body}\n", text)
    if count != 1:
        raise SystemExit(f"labeling function {name} not found once")
    return new


def mutate(target: Path, edit: dict) -> None:
    path = target / edit["file"]
    text = path.read_text(encoding="utf-8")
    if "function" in edit:
        text = set_function_body(text, edit["function"], edit["body"])
    else:
        if text.count(edit["old"]) != 1:
            raise SystemExit(f"{target}: edit text not found once: {edit['old']!r}")
        text = text.replace(edit["old"], edit["new"])
    path.write_text(text, encoding="utf-8")
    if edit["file"] == "reward_machine.txt":  # keep the stored compiler text equal to the machine
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "compiler_text" in manifest.get("generation", {}):
            manifest["generation"]["compiler_text"] = text
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def build(item: dict, copies: Path) -> None:
    target = copies / item["set"] / item["suite"] / item["arm"] / item["name"]
    if target.exists():
        raise SystemExit(f"{target} exists: remove S/copies first")
    kind, source = item["source"]["kind"], item["source"]["path"]
    if kind == "git":
        copy_from_git(item["source"]["commit"], source, target)
    else:
        copy_folder(Path(source), target)
    if kind == "level-bench":
        put_level_bench_run(item["source"]["run"], target)
    for edit in item.get("edits", []):
        mutate(target, edit)


def main() -> None:
    study = Path(sys.argv[1])
    spec = json.loads((study / "spec.json").read_text(encoding="utf-8"))
    for item in spec:
        build(item, study / "copies")
    print(f"{len(spec)} copies built under {study / 'copies'}")


if __name__ == "__main__":
    main()
