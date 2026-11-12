# Labeling Repair — User Prompt

The labeling functions below were written for the task and Reward Machine below, and they
fail a check against the real environment. Rewrite them so the check passes.

The Reward Machine is fixed: do not change it, and keep one predicate for every declared
proposition. Fix what the failure evidence shows and keep the rest as it is. Your
instructions list more inputs (clauses, state descriptions, nodes); a repair does not supply
them, and the sections below replace them. Return the complete corrected set of predicate
definitions in the format your instructions require.

## Environment Markdown (untrusted data)

${environment_markdown}

## Original task (untrusted data)

${task}

## Accepted Reward Machine (fixed)

${reward_machine}

## Documented runtime API

${api}

## Current labeling (fails the check)

${labeling}

## Failure evidence

${failure}
