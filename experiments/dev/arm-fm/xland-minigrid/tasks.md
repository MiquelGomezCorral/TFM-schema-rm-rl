# Tasks

## Reported evaluation set

`XLAND-1000` — The first 1,000 rulesets from the XLand-MiniGrid `medium-1m`
benchmark. Each ruleset is a separate task combining one goal, transformation rules,
and initial objects.

The paper identifies the set but does not publish its decoded 1,000 natural-language
task prompts or generated RMs. Recreate the set from the benchmark data rather than
inventing replacements.

## Reported concrete example

`XLAND-EX-1` — Place the blue pyramid near the purple square to create a red circle,
then move the red circle to the green goal.

This task is stated in the caption of Figure 16. The distractor yellow circle can make
the sampled task unsolvable.

## Reproducible subsets

- 1-task plot: seed `197`.
- 3-task plot: seeds `212`, `197`, `260`.
- 5-task plot: add `859`, `594`.
- 10-task plot: add `571`, `602`, `751`, `660`, `616`.

The paper provides the seeds but not their decoded text in the manuscript.

## Evidence

- Paper Sections 3.4, 4, and Appendix A.2.4: `docs/ARM-FM/ARM-FM.md`.
- Benchmark source: <https://github.com/corl-team/xland-minigrid>.
