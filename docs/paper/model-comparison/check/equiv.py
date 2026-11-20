"""Do two hard clause sets accept exactly the same finite traces? Exact check on the compiled DFAs.

    PYTHONPATH=<E>/app python equiv.py '<json set 1>' '<json set 2>'
    a set is [[template, [propositions...]], ...]; every clause is read as hard.

Each clause is compiled the pipeline's way (ltlf_of -> FL-AT/MONA compile_dfa). A breadth-first
search walks the product of every clause DFA of both sets over all valuations of the union
alphabet; the sets are equal iff "all of set 1 accept" == "all of set 2 accept" in every reachable
product state. Prints EQUAL with the product size, or the shortest trace that tells them apart.
"""

import itertools
import json
import sys
from collections import deque

from src.compiler.pipeline import compile_dfa
from src.compiler.reward_machine import evaluate_boolean_guard, parse_boolean_guard
from src.utils.presentation import ltlf_of


def automaton(template, names, alphabet):
    dfa = compile_dfa(ltlf_of(template, names))
    rows = {}
    for (source, guard), destination in dfa["transitions"].items():
        rows.setdefault(source, []).append((parse_boolean_guard(guard, alphabet), destination))
    return dfa["initial_state"], dfa["accepting_states"], rows


def step(rows, state, valuation):
    hits = {d for guard, d in rows[state] if evaluate_boolean_guard(guard, valuation)}
    if len(hits) != 1:
        raise ValueError(f"DFA not deterministic/complete at {state}: {hits}")
    return hits.pop()


def main() -> None:
    first, second = (json.loads(arg) for arg in sys.argv[1:3])
    alphabet = sorted({n for _, names in first + second for n in names})
    machines = [automaton(t, n, alphabet) for t, n in first + second]
    split = len(first)
    valuations = [
        dict(zip(alphabet, bits, strict=True))
        for bits in itertools.product((False, True), repeat=len(alphabet))
    ]

    def verdicts(states):
        accept = [s in m[1] for s, m in zip(states, machines, strict=True)]
        return all(accept[:split]), all(accept[split:])

    start = tuple(m[0] for m in machines)
    seen, queue = {start: []}, deque([start])
    while queue:
        states = queue.popleft()
        one, two = verdicts(states)
        if one != two:
            trace = [sorted(k for k, v in val.items() if v) for val in seen[states]]
            print(
                f"DIFFERENT: set 1 {'accepts' if one else 'rejects'}, set 2 {'accepts' if two else 'rejects'} the trace {trace}"
            )
            return
        for valuation in valuations:
            nxt = tuple(step(m[2], s, valuation) for s, m in zip(states, machines, strict=True))
            if nxt not in seen:
                seen[nxt] = seen[states] + [valuation]
                queue.append(nxt)
    print(
        f"EQUAL over alphabet {alphabet}: {len(seen)} reachable product states, {len(valuations)} valuations each, every one agrees"
    )


if __name__ == "__main__":
    main()
