# Environment files

Back to the [main page](../README.md).

FARM reads one Markdown file per environment, `environment.md`. It is written once, in plain
words, and every task in that environment uses it.

A full example: [`experiments/benchmark/envs/minigrid-doorkey/environment.md`](../experiments/benchmark/envs/minigrid-doorkey/environment.md).

## The one strict part: the propositions

The file is free prose, except for one section that lists the propositions, the events and
facts that a task can speak of:

```markdown
## Propositions
- `p1`: Passenger 1 entered the taxi.
- `d1`: Passenger 1 was delivered.
```

- **One line per proposition**, in exactly this shape.
- **Names** use lowercase letters, digits and `_`, start with a letter or `_`, and are unique.
  `true` and `false` are not allowed.
- **A mistake** stops the run with a message that points to the line.

The generator can only use the names in this list.

## The code goes in a second file

`environment.md` holds facts only. What the labelling code may read from the live environment
goes in `environment-code.md`, next to it, under a `## Labeling API` section. It is needed only
to generate labelling functions or to train.

## Writing a new one

The full guide, with the sections a description should have, is
[docs/ENVIRONMENT_AUTHORING.md](../docs/ENVIRONMENT_AUTHORING.md).
