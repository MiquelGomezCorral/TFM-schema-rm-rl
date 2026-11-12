# Prompt budget: worked examples per pipeline

Counted from `app/src/prompts/**` at commit `42bc2f0`. No prompt was changed for this count.

A worked example is a task wording followed by the answer the model should give for it: a
clause set, or a critic verdict. Output skeletons ("Return only: REWARD_MACHINE: ...") and
`such as` illustrations are not counted.

## FARM (compiler) prompts

| Prompt file | Lines | Role it reaches | Worked examples |
| --- | --- | --- | --- |
| `app/src/prompts/compiler-rm/declare-templates.md` | 40-53 | task-to-clause examples; inserted into the creator and critic system prompts | 5 |
| `app/src/prompts/compiler-rm/reward-machine-critic.system.md` | 117-157 | critic system prompt, section "Worked example" | 7 (5 with a JSON verdict, 2 described in prose) |
| `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md` | none | clause creator | 0 |
| `app/src/prompts/compiler-rm/reward-machine-tagger.system.md` | none | state description tagger | 0 |
| `app/src/prompts/compiler-rm/labeling-generator.system.md` | none | labeling generator | 0 |
| `app/src/prompts/compiler-rm/labeling-reviewer.system.md` | none | labeling critic | 0 |

What each FARM model reads: the clause creator 5 examples, the reward-machine critic 12
(5 from `declare-templates.md`, 7 of its own), the tagger and both labeling roles none.

## ARM-FM prompts

| Prompt file | Role | Worked examples |
| --- | --- | --- |
| `app/src/prompts/arm_fm/rm_generator.{system,user}.md` | machine generator | 0 |
| `app/src/prompts/arm_fm/rm_critic.{system,user}.md` | machine critic | 0 |
| `app/src/prompts/arm_fm/labeling_generator.{system,user}.md` | labeling generator | 0 |
| `app/src/prompts/arm_fm/labeling_critic.{system,user}.md` | labeling critic | 0 |
| `app/src/prompts/arm_fm/description_generator.{system,user}.md` | state description generator | 0 |

What each ARM-FM model reads: no worked example in any role. The machine generator reads an
output skeleton (the paper format) and seven rules instead.

## What this means for the comparison

FARM's two reasoning roles (clause creator, machine critic) carry worked examples; ARM-FM's carry
none. A FARM versus ARM-FM difference therefore mixes the pipelines' design with the prompt help
each one gets. Options for the user: keep the prompts as they are and state the asymmetry in the
paper, give ARM-FM matching examples, or remove the FARM examples for a control run.

decision: pending
