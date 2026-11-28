# Engines: the language-model providers

An engine is the code that sends a request to one provider and reads its answer. FARM has four.
Choose one with `LLM_PROVIDER` in `.env` (see `example.env` at the root of the repository).

| `LLM_PROVIDER` | What it is | Variables in `.env` |
| --- | --- | --- |
| `openai` (default) | The OpenAI API | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `opencode` | The OpenCode API | `OPENCODE_API_KEY`, `OPENCODE_MODEL`, and `OPENCODE_BASE_URL` (optional, default `https://opencode.ai/zen/v1`) |
| `antigravity` | A Google subscription, through the `agy` program | `ANTIGRAVITY_MODEL`. No API key |
| `local` | Any server that speaks the OpenAI API, such as vLLM or Ollama | `LOCAL_LLM_BASE_URL`, `LOCAL_MODEL`, and optionally `LOCAL_LLM_SERVER` (`vllm` or `ollama`) and `LOCAL_LLM_API_KEY` |

Any other value stops the run with `Unsupported LLM_PROVIDER`.

## A different model for the generator and the critic

Each provider reads `<PROVIDER>_MODEL`. To give the two roles different models, add
`<PROVIDER>_MODEL_GENERATOR` and `<PROVIDER>_MODEL_CRITIC`, for example
`OPENCODE_MODEL_CRITIC`.

## The model must support structured output

Every engine asks for the answer as JSON that follows a fixed schema. A model that cannot do
this returns an error. Nothing is retried with another model.

## Antigravity

Antigravity is not installed by `setup.sh`. Install it with the
[official command](https://antigravity.google/docs/cli/install/), run `agy` once to log in, and
list the models:

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
agy
agy models
```

Then set the provider and one of the listed models:

```dotenv
LLM_PROVIDER=antigravity
ANTIGRAVITY_MODEL=<name from agy models>
```

It uses the login that `agy` keeps on your machine, so every request spends your subscription
quota. FARM starts `agy` without tools and without asking anything on screen.

## Files

- `provider_engines.py`: one engine per provider.
- `structured.py`: the JSON schemas of the answers, and the checks on each answer.
