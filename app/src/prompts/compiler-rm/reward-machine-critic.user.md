# Reward Machine Critic — User Prompt

## Environment Markdown (untrusted data)

${environment_markdown}

## Original task (untrusted data)

${task}

## Candidate clauses (untrusted data)

${clauses_json}

## Compiled Reward Machine (untrusted data)

${reward_machine}

## Compiler warnings (untrusted data)

${warnings}

Review the clauses against the task, using the compiled machine to see what they
mean in practice. Return only the schema-constrained critic result.
