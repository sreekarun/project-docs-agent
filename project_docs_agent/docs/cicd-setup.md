# CI/CD bootstrap (one-time)

This is what was done on 2026-11-12 to stand up staging, production and the GitHub
Actions pipeline. Re-run it only to rebuild from scratch or to reproduce the setup
in other projects. Day-to-day releases need none of this — see
[release-process.md](release-process.md).

## 1. Tools

```bash
brew install uv gh hashicorp/tap/terraform
uvx google-agents-cli setup --skip-auth    # agents-cli + coding-agent skills
gcloud auth login && gcloud auth application-default login
```

Versions used: agents-cli 1.14.0, Terraform 1.17.2, uv 0.13.8, Cloud SDK 593.

## 2. GitHub CLI with the `workflow` scope

Terraform writes Actions secrets/variables and environments, which needs `workflow`
in addition to `repo`:

```bash
gh auth refresh -h github.com -s workflow
gh api -i user | grep -i x-oauth-scopes   # must list: repo, workflow
```

`infra cicd` fails fast with `GitHub CLI authentication lacks required scopes:
workflow` otherwise. The refresh only takes effect after the browser device-code
step completes and the terminal prints "Authentication complete".

## 3. GCP projects

```bash
gcloud projects create adk-chatbot-staging --name=adk-chatbot-staging
gcloud projects create adk-chatbot-prod    --name=adk-chatbot-prod
gcloud billing projects link adk-chatbot-staging --billing-account=<BILLING_ACCOUNT_ID>
gcloud billing projects link adk-chatbot-prod    --billing-account=<BILLING_ACCOUNT_ID>
```

No APIs need enabling by hand — Terraform does it. Production also hosts the CI/CD
resources (`--cicd-project` defaults to the prod project).

## 4. Add the pipeline scaffolding

```bash
agents-cli scaffold enhance . --cicd-runner github_actions --region us-east4 \
  --agent-guidance-filename CLAUDE.md --dry-run   # preview
agents-cli scaffold enhance . --cicd-runner github_actions --region us-east4 \
  --agent-guidance-filename CLAUDE.md -y
```

Adds `.github/workflows/{pr_checks,staging,deploy-to-prod}.yaml`,
`deployment/terraform/cicd/`, and `tests/load_test/`. With `-y`, conflicting files
(`README.md`) keep the local version.

## 5. Production approval gate (local Terraform change)

The template creates the `production` environment without protection rules, so
prod would deploy automatically after staging. We added a required reviewer in
`deployment/terraform/cicd/github.tf`:

```hcl
reviewers {
  users = [586996]   # GitHub user sreekarun (gh api user -q .id)
}
```

Re-check this block after any `agents-cli scaffold upgrade`.

## 6. Plan, then apply

```bash
agents-cli infra cicd --staging-project adk-chatbot-staging --prod-project adk-chatbot-prod \
  --repository-name adk-chatbot --repository-owner sreekarun \
  --cicd-runner github_actions --region us-east4            # plan only
# same command + --apply
```

- The plan step already creates the state bucket
  `gs://adk-chatbot-prod-terraform-state` and writes `vars/env.tfvars` and
  `backend.tf` files (these are committed).
- Result: `94 added, 0 changed, 0 destroyed` (outputs in
  [architecture.md](architecture.md#projects-and-environments)).

## 7. Verify model access in the new projects

```bash
TOKEN=$(gcloud auth print-access-token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://aiplatform.googleapis.com/v1/projects/adk-chatbot-staging/locations/global/publishers/google/models/gemini-3.8-flash:generateContent" \
  -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}'
```

(Repeat for `adk-chatbot-prod`.)

## 8. First pipeline run

Commit everything and push to `main`. The push touches `deployment/**` and
`tests/**`, so *Deploy to Staging* runs, then *Deploy to Production* waits for
approval. Terraform created the runtimes with placeholder code; the first pipeline
run replaces it with the real agent.

## 9. Retire the old runtime

The pre-pipeline runtime `projects/sreeai-noorg/locations/us-east4/reasoningEngines/7387508675864166400`
(created by `adk deploy`, later updated by `agents-cli deploy`) was deleted on
2026-11-12, once the pipeline's staging runtime was validated. See [history.md](history.md).
