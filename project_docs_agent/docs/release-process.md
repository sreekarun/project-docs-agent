# Release process

Every change reaches production through GitHub Actions. Nobody runs
`agents-cli deploy` against staging or production by hand.

```
feature branch ──PR──▶ PR checks ──merge──▶ Deploy to Staging ──▶ load test
                       (unit +              (adk-chatbot-staging)     │
                        integration)                                  ▼
                                                     Deploy to Production
                                                     waits for approval ──▶ adk-chatbot-prod
```

## 1. Open a pull request

Workflow: `.github/workflows/pr_checks.yaml` — runs on PRs to `main` that touch
`chatbot/**`, `tests/**`, `deployment/**` or `uv.lock`.

- `uv run pytest tests/unit`
- `uv run pytest tests/integration` — runs the agent in-process against the real
  model, authenticated to the CI/CD project (`adk-chatbot-prod`) through Workload
  Identity Federation.

PRs that only touch docs, `README.md` or `CLAUDE.md` skip the checks.

## 2. Merge to `main` → staging

Workflow: `.github/workflows/staging.yaml` (same path filter as above).

1. `agents-cli deploy --project adk-chatbot-staging --region us-east4`, keeping the
   runtime's existing identity (no `--service-account`; see
   [architecture.md](architecture.md#runtime-identity-agent-identity)). It updates the staging runtime in place
   (matched by display name `adk-chatbot`).
2. Load test: 30 s of Locust against staging (`tests/load_test/`); results are
   copied to `gs://<staging logs bucket>/load-test-results/`.
3. On success it calls the production workflow.

> A push that touches none of the filtered paths does **not** deploy. To deploy
> anyway (e.g. after a root-level config fix), start it manually — this
> `workflow_dispatch` trigger is a local addition to the template:
> `gh workflow run staging.yaml --ref main` or Actions → *Deploy to Staging* →
> *Run workflow*. It still flows on to the gated production job.

## 3. Approve → production

Workflow: `.github/workflows/deploy-to-prod.yaml` (job environment `production`).

The `production` GitHub environment has a required reviewer (`sreekarun`, set in
`deployment/terraform/cicd/github.tf`), so the job pauses:

1. GitHub → **Actions** → the *Deploy to Staging* run → *call_production_workflow*.
2. **Review deployments** → tick `production` → **Approve and deploy**.

It then runs `agents-cli deploy --project adk-chatbot-prod --region us-east4`.

`deploy-to-prod.yaml` also has `workflow_dispatch`, so a prod redeploy of the
current `main` can be started from the Actions tab (still needs approval).

## 4. Verify

See [operations.md](operations.md#test-a-deployed-agent). At minimum send one
prompt to staging after the staging job and to prod after approval.

## Rollback

Agent Runtime has no revision rollback. Revert the offending commit on `main`
(`git revert <sha>` → PR → merge); the pipeline redeploys the previous code.
