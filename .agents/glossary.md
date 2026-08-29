# Glossary

## Terms

- Proposition: stable environment event identifier declared in environment Markdown.
- DECLARE template: constrained temporal behavior pattern selected from IBM `nl2ltl`.
- LTLf: Linear Temporal Logic interpreted over finite traces.
- DFA: deterministic finite automaton generated from an LTLf formula.
- Guard: Boolean condition over propositions labeling an automaton or Reward Machine transition.
- MONA: external decision-procedure executable used by FL-AT to compile LTLf-derived logic into a DFA.
- Reward Machine (RM): finite-state reward specification with guarded transitions and edge rewards.
- Compilation proposal: inspectable instruction, DECLARE pattern, grounded propositions, LTLf formula, and LLM-proposed reward awaiting human approval.
