# Local development

## Prerequisites

| Tool | Install | Why |
|---|---|---|
| Google Cloud SDK | <https://cloud.google.com/sdk/docs/install> | ADC auth, logs |
| uv | `brew install uv` | Python env + deps (Python 3.11–3.13; 3.14 is not supported by the template) |
| agents-cli | `uvx google-agents-cli setup` | build / run / eval / deploy; also installs the `google-agents-cli-*` coding-agent skills |
| gh (optional) | `brew install gh` | Only needed for CI/CD bootstrap |
| Terraform (optional) | `brew install hashicorp/tap/terraform` | Only needed for CI/CD bootstrap |

## Setup

```bash
git clone https://github.com/sreekarun/adk-chatbot.git && cd adk-chatbot
agents-cli install                       # uv sync into .venv
gcloud auth application-default login    # model calls use ADC
cp .env.example .env                     # project env (agents-cli)
cp .env.example chatbot/.env             # read by the ADK loader
```

Edit both `.env` files:

```dotenv
GOOGLE_GENAI_USE_ENTERPRISE=1
GOOGLE_CLOUD_PROJECT=<your dev project, e.g. sreeai-noorg>
GOOGLE_CLOUD_LOCATION=global
# Optional — these are the defaults in chatbot/agent.py:
MODEL_NAME=gemini-3.8-flash
MODEL_LOCATION=global
```

Both files are gitignored. Never commit them.

## Run

```bash
agents-cli run "hello"        # one-shot, starts a temporary local server
agents-cli playground         # web UI on http://127.0.0.1:8080
uv run adk run chatbot        # raw ADK interactive CLI (also works)
```

## Test

```bash
uv run pytest tests/unit                          # no cloud access needed
uv run --env-file .env pytest tests/integration   # calls the real model
agents-cli lint                                   # ruff, codespell, ty
agents-cli eval run                               # behavioural evals (tests/eval/)
```

`pytest` does not load `.env` by itself — without `--env-file .env` the
integration test fails with `ValueError: Gemini API does not support
project/location` (the SDK falls back to API-key mode, which rejects the pinned
model location). CI sets these variables explicitly.

Behaviour checks belong in evals, not pytest assertions on model text.

## Making a change

1. Branch from `main`.
2. Edit `chatbot/agent.py` (keep `root_agent` and `app = App(..., name='chatbot')`
   exported; don't change the model unless that's the point of the change).
3. `agents-cli run "<prompt that exercises it>"`, run tests, add an eval case.
4. Open a PR — see [release-process.md](release-process.md).
