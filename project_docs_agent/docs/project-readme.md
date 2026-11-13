# ADK Chatbot

A simple chatbot application built using **Google Agent Development Kit (ADK) 2.0** integrated with the **Gemini Enterprise Agent Platform (GEAP)**.

## Overview
- **Framework:** Google ADK 2.0 (`google-adk`)
- **Platform:** Gemini Enterprise Agent Platform (GEAP)
- **Model:** `gemini-3.8-flash`
- **Runtime:** Python 3.11–3.13 (uv)
- **Tooling:** agents-cli (build, eval, deploy to Agent Runtime)

## Getting Started

Build, run and deploy use [agents-cli](https://google.github.io/agents-cli/)
(`uvx google-agents-cli setup`, needs [uv](https://docs.astral.sh/uv/)).

### 1. Install dependencies
```bash
agents-cli install        # uv sync into .venv (Python 3.11-3.13)
```

### 2. Configure GEAP credentials
```bash
gcloud auth application-default login
cp .env.example .env              # project env, propagated on deploy
cp .env.example chatbot/.env      # read by the ADK loader locally
```
Set:
- `GOOGLE_GENAI_USE_ENTERPRISE=1`
- `GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id`
- `GOOGLE_CLOUD_LOCATION=global`
- `MODEL_NAME=gemini-3.8-flash` and `MODEL_LOCATION=global` (optional; these are the defaults)

### 3. Run locally
```bash
agents-cli run "hello"    # one-shot smoke test
agents-cli playground     # web playground
```

### 4. Deploy

Deployment is automated: merge to `main` → GitHub Actions deploys to **staging**,
then to **production** after manual approval. Infrastructure is Terraform
(`deployment/terraform/cicd/`).

## Documentation

See [`docs/`](docs/README.md) — architecture, local development, CI/CD bootstrap,
release process, operations and troubleshooting.
