# adk-chatbot documentation

How this agent is built, tested, deployed and operated.

| Doc | Read it when |
|---|---|
| [architecture.md](architecture.md) | You want the big picture: code, environments, GCP projects, pipeline |
| [local-development.md](local-development.md) | Setting up a machine, running and testing the agent locally |
| [cicd-setup.md](cicd-setup.md) | Bootstrapping (or rebuilding) the GCP projects, Terraform and GitHub Actions — one-time |
| [release-process.md](release-process.md) | Shipping a change: PR → staging → approval → production |
| [operations.md](operations.md) | Testing deployed agents, logs, config, troubleshooting, known gotchas |
| [history.md](history.md) | Developer journey: each step, what broke and why, lessons, current state and next steps |

## Quick reference

| What | Value |
|---|---|
| Repo | `sreekarun/adk-chatbot` (public) |
| Agent code | `chatbot/agent.py` (`root_agent`, `app`) |
| Model | `gemini-3.8-flash` via the `global` endpoint (`MODEL_NAME`, `MODEL_LOCATION`) |
| Tooling | [agents-cli](https://google.github.io/agents-cli/) 1.14, uv, Terraform |
| Staging project | `adk-chatbot-staging` |
| Production + CI/CD project | `adk-chatbot-prod` |
| Region | `us-east4` |
| Dev/sandbox project | `sreeai-noorg` (local development only) |
