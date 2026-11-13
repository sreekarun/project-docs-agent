# Operations

## Test a deployed agent

```bash
# staging
agents-cli run --mode adk "hello" --url \
  https://us-east4-aiplatform.googleapis.com/v1/projects/adk-chatbot-staging/locations/us-east4/reasoningEngines/1601509054599921664
# production
agents-cli run --mode adk "hello" --url \
  https://us-east4-aiplatform.googleapis.com/v1/projects/adk-chatbot-prod/locations/us-east4/reasoningEngines/721618277402411008
```

`--url` must be the full `https://<region>-aiplatform.googleapis.com/v1/...` URL; a
bare resource name fails with "Agent Runtime URL with a missing location".

SDK alternative:

```python
import vertexai

c = vertexai.Client(project="adk-chatbot-prod", location="us-east4")
ae = c.agent_engines.get(
    name="projects/adk-chatbot-prod/locations/us-east4/reasoningEngines/721618277402411008"
)
for ev in ae.stream_query(user_id="smoke-test", message="hello"):
    print(ev)
```

Console playground: Vertex AI → Agents → Agent Engines (us-east4) → `adk-chatbot`.

## Logs and telemetry

```bash
gcloud logging read 'resource.type="aiplatform.googleapis.com/ReasoningEngine"' \
  --project adk-chatbot-prod --limit 50
```

- Traces: Cloud Trace in each project (`GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true`).
- GenAI telemetry is routed by a log sink into BigQuery `adk_chatbot_telemetry`
  (message content is **not** captured: `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false`).
- Load-test reports: `gs://adk-chatbot-staging-adk-chatbot-logs/load-test-results/`.

## Configuration

| Variable | Where set | Notes |
|---|---|---|
| `GOOGLE_GENAI_USE_ENTERPRISE` | Terraform + pipeline `--update-env-vars`, `.env` locally | Enterprise/Vertex backend. Don't also set `GOOGLE_GENAI_USE_VERTEXAI`: with no `.env` in CI, agents-cli would add both, so the workflows pass `GOOGLE_GENAI_USE_ENTERPRISE=true` and `--remove-env-vars=GOOGLE_GENAI_USE_VERTEXAI` |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` | Agent Runtime / Terraform | Runtime location = region; model location is separate |
| `MODEL_NAME` | default in `agent.py` | `gemini-3.8-flash` |
| `MODEL_LOCATION` | default in `agent.py` | `global` — required for this model on a regional runtime |
| `LOGS_BUCKET_NAME`, `OTEL_*` | pipeline `--update-env-vars` / Terraform | telemetry |
| `AGENT_REGISTRY_ENABLED` | pipeline: `true` in staging, GitHub var `AGENT_REGISTRY_ENABLED_PROD` in prod | Gives the chatbot `find_agents` / `ask_agent`: it lists Agent Registry (cached 60 s) and calls the chosen agent over A2A at the `.../api/a2a/<app>` interface from its stored card (Agent Runtime's native `.../a2a` endpoint rejects these containers). Optional `AGENT_REGISTRY_PROJECT` / `AGENT_REGISTRY_LOCATION`. Needs `roles/agentregistry.viewer` on the identity |
| Runtime size | pipeline `--max-instances 1 --concurrency 3 --cpu 1 --memory 1Gi`; staging `--min-instances 1`, prod `--min-instances 0` | PoC sizing at Agent Runtime minimums: at most 1 instance, 3 concurrent requests. Staging keeps 1 warm instance (~$69/month) so development isn't slowed by cold starts; prod scales to zero (idle costs nothing; the first request after idle has a cold start). Terraform's `deployment_spec` (min 1, 4 vCPU, 8 GiB) only applies at creation; raise these flags for real traffic |
| `GCSFS_EXPERIMENTAL_ZB_HNS_SUPPORT` | pipeline `--update-env-vars` | `false`: gcsfs skips its Storage Control bucket-type lookup, which returns 401 under Agent Identity ("Could not determine bucket type ... falling back to GCSFileSystem") on every completion upload. The logs bucket is a standard regional bucket, so the plain filesystem is the right one |

Secrets: store in Secret Manager in the target project and pass via
`agents-cli deploy --secrets ENV=SECRET[:VERSION]` in the workflow; grant
`roles/secretmanager.secretAccessor` to the runtime's Agent Identity principal
(add it to `var.agent_identity_roles` or a dedicated binding in `iam.tf`).

## Terraform

- CI/CD + staging + prod stack: `deployment/terraform/cicd/`, state
  `gs://adk-chatbot-prod-terraform-state` (prefix per stack). Change it by editing
  the `.tf` files and re-running `agents-cli infra cicd ... --apply` (plan first
  without `--apply`).
- `deployment/terraform/single-project/` (template dev stack) is **not applied**.
  Don't run `agents-cli infra single-project --apply` without a decision: it would
  create another runtime and telemetry stack in `sreeai-noorg`.
- Terraform cannot adopt a runtime that `agents-cli deploy` created outside it;
  use `terraform import` if that ever becomes necessary.

## Switching a runtime to Agent Identity

Changing the runtime resource through Terraform makes the provider resend the
whole spec, **including the placeholder source** (despite `ignore_changes`), so the
runtime ends up serving Google's "Hello from Cloud Run" image. Order of operations:

1. Targeted `terraform plan` of the runtime + its `agent_identity_roles` /
   `agent_identity_logs_bucket` entries. Apply the runtime first: the IAM members
   depend on `effective_identity`, which only becomes the agent principal *after* the
   switch, so a combined first apply fails with "Provider produced inconsistent
   final plan". Then re-plan and apply the IAM bindings.
2. Make sure the workflows on `main` don't pass `--service-account`.
3. Redeploy the code through the pipeline (`gh workflow run staging.yaml --ref main`
   for staging; approve the production job for prod).
4. Verify: `agents-cli run --mode adk "hello" --url ...`, then check logs for
   `PERMISSION_DENIED`.

Phase 2 (prod, plus removing the old `adk-chatbot-app` SAs and the
`APP_SERVICE_ACCOUNT_*` GitHub variables) is the full `agents-cli infra cicd ...
--apply`, followed by an approved prod deploy.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 404 `Publisher model ... gemini-3.8-flash was not found` | Model called in a region. Keep `MODEL_LOCATION=global` and the `client_kwargs` pin in `agent.py` |
| Local pytest: `Gemini API does not support project/location` | `.env` not loaded: `uv run --env-file .env pytest ...` |
| `infra cicd`: `lacks required scopes: workflow` | `gh auth refresh -h github.com -s workflow`, finish the browser step |
| Push to `main` didn't deploy | Path filter: only `chatbot/**`, `tests/**`, `deployment/**`, `uv.lock` trigger staging |
| Prod job stuck "Waiting" | Expected — approve via *Review deployments* |
| WIF / auth failures in Actions | Re-run `agents-cli infra cicd ... --apply`; IAM can take a few minutes to propagate |
| Agent errors after deploy | Logs query above; look for import errors (`app` must be exported from `chatbot/agent.py`) |
| `agents-cli deploy` created a second runtime | Display name changed. The pipeline matches on `adk-chatbot` (manifest `name`) — don't rename |
| CI deploy: `403 ... aiplatform.reasoningEngines.get` on a runtime in another project | `deployment_metadata.json` has a stale `remote_agent_runtime_id`; agents-cli targets that ID before matching by display name. Keep the committed file at `null` values (a local `agents-cli deploy` rewrites it — don't commit that). Happened on the first pipeline run, 2026-11-12 |
| Deploy: `400 FAILED_PRECONDITION: Cannot set spec.service_account when spec.identity_type is AGENT_IDENTITY` | The workflow passes `--service-account` to an Agent Identity runtime. Remove the flag (agents-cli keeps the existing identity) |
| Runtime returns HTML / "Hello from Cloud Run", or session create fails with `invalid JSON ... unexpected character: '<'` | A Terraform update to the runtime reset its code to the placeholder image. Redeploy through the pipeline (`gh workflow run staging.yaml --ref main`) |
| `terraform apply`: `Provider produced inconsistent final plan` on `agent_identity_roles` / `agent_identity_logs_bucket` | The plan used the old `effective_identity`. Apply the runtime switch first, then re-plan and apply the IAM bindings |
| Logs: `Could not determine bucket type ... 401 ... falling back to GCSFileSystem` | gcsfs's Storage Control lookup rejects Agent Identity credentials (uploads still work). Set `GCSFS_EXPERIMENTAL_ZB_HNS_SUPPORT=false` in the workflow's `--update-env-vars` |
| `Failed to resolve AgentCard ... (HTTP 401)` for `ai_news_agent` | Agent Identity tokens are bound to the runtime's certificate and only accepted over mTLS on `*.mtls.googleapis.com`. A plain bearer call to the normal host gets 401 (a 403 would be IAM). `chatbot/remote_agents.py` presents the client cert and rewrites requests to the mTLS host; any new hand-built Google API client needs the same |
| Python 3.14 errors | Template requires `>=3.11,<3.14`; recreate with `agents-cli install` |
