# Developer journey

How this project got from a local ADK script to a gated staging → prod pipeline,
including what broke along the way and why. Dates are local (US Pacific). For the
current procedures, see the other docs. This file records how we got there.

Repo: `sreekarun/adk-chatbot`. PRs and workflow runs are linked where they exist.

## Current state (2026-11-12)

| | Staging (`adk-chatbot-staging`) | Prod (`adk-chatbot-prod`) |
|---|---|---|
| Runtime | `1601509054599921664` | `721618277402411008` |
| Code | Current agent (deployed by the pipeline) | Terraform placeholder image (never deployed) |
| Identity | Agent Identity | `adk-chatbot-app` service account |
| Validated | Yes: prompt test, load test, logs, telemetry uploads | No |
| Size | 4 vCPU / 8 GiB, 1 warm instance → **0 warm, max 1, 1 vCPU / 1 GiB** on the next pipeline deploy | 4 vCPU / 8 GiB, 1 warm instance (until its first deploy) |

**Next steps**

1. **Agent Identity phase 2 (prod):** plan, then `agents-cli infra cicd ... --apply`
   (switches prod, removes the `adk-chatbot-app` SAs and `APP_SERVICE_ACCOUNT_*`
   GitHub variables), then an approved prod deploy. The apply resets prod to the
   placeholder, so the deploy must come after it. See
   [operations.md](operations.md#switching-a-runtime-to-agent-identity).
2. **Prod sizing:** prod keeps the template default (1 warm 4 vCPU / 8 GiB
   instance) until its first approved deploy applies the PoC sizing.
3. **Registry discovery in prod:** set `AGENT_REGISTRY_ENABLED_PROD=true` only after
   the agents it should find are deployed in prod (the news agent runs the
   placeholder until its first approved deploy), and grant the prod identity
   `roles/agentregistry.viewer`.

---

## 1. Scaffold (2026-11-10)

ADK 2.x agent in `chatbot/`, run locally with `adk run` against GEAP in
`sreeai-noorg`.

- The model went through several values (`gemini-3.8-flash`, `gemini-2.5-flash`,
  `gemini-3.8-flash-lite`, back to `gemini-3.8-flash`) while getting the location
  right. It ended on `gemini-3.8-flash` via `global`.

## 2. Claude Code setup (2026-11-12)

- Added `CLAUDE.md` and the project skill `.claude/skills/google-adk/`.
- The model now comes from `MODEL_NAME`, not code. Removed the real project ID from
  the README.
- **Problem:** pushing failed because GitHub already had an unrelated initial
  commit. **Fix:** merged with `--allow-unrelated-histories` (`39d2ddc`).

## 3. First deployment by hand (2026-11-12)

- `adk deploy agent_engine` to `sreeai-noorg` / us-east4 → runtime
  `7387508675864166400`.
- **Problem:** the deployed agent got 404 `Publisher model ... gemini-3.8-flash was
  not found`. Agent Runtime sets `GOOGLE_CLOUD_LOCATION` to its region, and this
  model is only served from `global`. **Fix:** added `MODEL_LOCATION` (default
  `global`) and built the model as `Gemini(model=..., client_kwargs={'location': ...})`
  (`2e7a064`). See [architecture.md](architecture.md#why-the-model-location-is-pinned).
- **Gotchas:**
  - `adk deploy --env_file` was ignored (the CLI changes directory first).
  - `agents-cli run --url` needs the full https URL, not the resource name.

## 4. Move to agents-cli (2026-11-12)

- `scaffold enhance --from-adk-project`, then `-d agent_runtime`. Added
  `app = App(root_agent=..., name='chatbot')`.
- Dependencies moved to `pyproject.toml` / `uv.lock`, pinned to Python 3.13 (the
  template needs `<3.14`).
- `agents-cli deploy` updated the same runtime in place, matched by display name
  `adk-chatbot` (`2b1d11b`).
- **Gotcha:** local integration tests failed with `Gemini API does not support
  project/location` because pytest doesn't load `.env`. Use
  `uv run --env-file .env pytest`.

## 5. Terraform + GitHub Actions (2026-11-12)

- Created `adk-chatbot-staging` and `adk-chatbot-prod`, added the GitHub Actions
  scaffolding, and applied the CI/CD Terraform with `agents-cli infra cicd` (94
  resources). See [cicd-setup.md](cicd-setup.md).
- **Local change to the template:** a required reviewer on the `production`
  environment (`github.tf`), so prod deploys wait for approval.
- **Problem:** `infra cicd` failed with `GitHub CLI authentication lacks required
  scopes: workflow`. **Fix:** `gh auth refresh -h github.com -s workflow`, completed
  in the browser.
- **Problem:** the first staging run
  ([43332753059](https://github.com/sreekarun/adk-chatbot/actions/runs/43332753059))
  failed with a 403 on the *old* `sreeai-noorg` runtime. agents-cli deploys to the
  runtime ID in `deployment_metadata.json` before matching by name, and the
  committed file still had the old ID. **Fix:** reset it to `null` values and added a
  `workflow_dispatch` trigger so staging can be redeployed without a code change
  (`7ad37c2`). The manual run
  ([43333211102](https://github.com/sreekarun/adk-chatbot/actions/runs/43333211102))
  succeeded.

## 6. Agent Identity, phase 1: staging (2026-11-12)

**Why:** the console's Identity / Topology / Security tabs were greyed out because
the runtimes ran as a service account (`identity_type = SERVICE_ACCOUNT`).

**Plan:** switch Terraform to `AGENT_IDENTITY` and grant roles to each runtime's
`effective_identity` principal. Full plan: 16 add, 2 change, 16 destroy, with runtime
IDs unchanged. The rollout was split so prod waits until staging is validated.

What happened:

1. **Auto mode blocked the apply.** Claude Code's auto-mode classifier denied
   `terraform apply`. **Fix:** a local permission rule `Bash(terraform apply:*)` in
   `.claude/settings.local.json` (gitignored), used only after the plan was reviewed.
2. **Targeted apply half-failed.** The runtime switched, but all 8 IAM grants failed
   with `Provider produced inconsistent final plan`. At plan time
   `effective_identity` was still the old SA. The real principal
   (`principal://agents.global.proj-<number>.system.id.goog/.../reasoningEngines/<id>`)
   only exists after the switch. **Fix:** re-planned and applied the grants as a
   second step.
3. **Staging served "Hello from Cloud Run".** The provider resends the whole spec,
   placeholder source included, on any update to the runtime, despite
   `ignore_changes` on the source. The test call got HTML back. **Lesson:** every
   Terraform change to the runtime must be followed by a pipeline deploy.
4. **The redeploy failed**
   ([43337229503](https://github.com/sreekarun/adk-chatbot/actions/runs/43337229503))
   with `400 FAILED_PRECONDITION: Cannot set spec.service_account when
   spec.identity_type is AGENT_IDENTITY`, because the workflow on `main` still passed
   `--service-account`. Staging stayed down until the workflow change was merged.
5. **[PR #1](https://github.com/sreekarun/adk-chatbot/pull/1)** merged the identity
   Terraform, dropped `--service-account` from both workflows, and fixed a second
   issue the deploy log showed: with no `.env` in CI, agents-cli set both
   `GOOGLE_GENAI_USE_ENTERPRISE` and `GOOGLE_GENAI_USE_VERTEXAI`. The workflows now
   pass `GOOGLE_GENAI_USE_ENTERPRISE=true` and
   `--remove-env-vars=GOOGLE_GENAI_USE_VERTEXAI`. Staging deployed
   ([43342771489](https://github.com/sreekarun/adk-chatbot/actions/runs/43342771489))
   and answered prompts.

## 7. gcsfs 401 warning (2026-11-12)

- **Problem:** after the switch, every completion upload logged `Could not determine
  bucket type for bucket name ...-logs: 401 Request had invalid authentication
  credentials ... falling back to GCSFileSystem`. gcsfs checks the bucket type
  through the Storage Control API, and that call rejects Agent Identity credentials.
  It's a 401, not a 403, so adding roles doesn't help. The fallback path worked and
  uploads still landed, but the check repeated on every upload.
- **Missed at first:** the post-deploy log check only searched for errors,
  `PERMISSION_DENIED` and 403. These lines have no severity and say 401, so it found
  nothing. You spotted them in the console. Check for 401s and unlabelled warnings
  too.
- **Fix: [PR #2](https://github.com/sreekarun/adk-chatbot/pull/2)** sets
  `GCSFS_EXPERIMENTAL_ZB_HNS_SUPPORT=false` in both workflows, so gcsfs uses the
  plain filesystem directly. That's the right choice for this standard regional
  bucket. Workflow-only changes don't match the staging path filter, so it was
  deployed manually
  ([43347938264](https://github.com/sreekarun/adk-chatbot/actions/runs/43347938264)).
  Afterwards: no warnings, and uploads still landed.

## 8. Cost trim for the PoC (2026-11-12)

- The Terraform template sizes each runtime at `min_instances = 1`, 4 vCPU, 8 GiB.
  At list price that's up to ~$300 per runtime per month if the warm instance is
  billed, far too much for a proof of concept with no users.
- The workflows now deploy at Agent Runtime's minimums: `--min-instances 0 --max-instances 1 --concurrency 3 --cpu 1 --memory 1Gi`
  (concurrency 3 = the recommended 2 × cpu + 1). No scaling is needed for a PoC.
  Terraform ignores `deployment_spec` after creation, so the deploy step is where
  sizing lives.
- Deleted the pre-pipeline runtime `sreeai-noorg/.../7387508675864166400` (it was
  scale-to-zero, but redundant).

## 9. AI news agent and A2A hand-off (2026-11-13)

- A second agent, `sreekarun/ai-news-agent`, was scaffolded as its own repo and
  deployed to the same staging/prod projects (its own runtime, WIF pool, CI SA,
  logs bucket and state prefix; the plan changed nothing of this project's).
- The chatbot discovers it through its A2A agent card: `NEWS_AGENT_CARD_URL`
  adds a `RemoteA2aAgent` sub-agent, and the chatbot transfers AI-news questions
  to it. Calls authenticate with the runtime's own Google credentials.
- **Problem:** the first staging test got `401` fetching the card. Agent Identity
  tokens are certificate-bound and only accepted over mTLS on
  `*.mtls.googleapis.com`; the hand-built httpx client sent a plain bearer token
  to the normal host (it worked locally with user credentials). **Fix:** present
  google-auth's client certificate and rewrite requests to the mTLS host. Same root
  cause as the gcsfs 401 in step 7: hand-rolled Google API calls must do what the
  client libraries do under Agent Identity.

## 10. Dynamic discovery through Agent Registry (2026-11-13)

- Agent Runtime registers every deployed agent in Agent Registry, including the
  A2A card each deploy stores. The chatbot replaced its fixed news sub-agent
  (`NEWS_AGENT_CARD_URL`) with `find_agents` / `ask_agent` tools that list the
  registry at request time and call the chosen agent over A2A.
- **Gotcha:** the registry advertises Agent Runtime's native `.../a2a` endpoint,
  which rejects these containers ("does not have A2A methods defined"). The
  working endpoint is the `.../api/a2a/<app>` interface listed in the stored card.
- **Gotcha:** the news agent crashed on A2A calls with
  `'dict' object has no attribute 'model_dump'` in `VertexAiSessionService` because
  `propagate_grounding_metadata=True` was set on its `AgentTool` (fixed in
  ai-news-agent PR #2).
- Staging keeps 1 warm instance per agent (~$69/month each) so cold starts don't
  slow development.

## Lessons

- Plan, review, then apply. Split identity changes: the runtime first, then the IAM
  grants that depend on its new principal.
- Terraform owns the runtime's *shape*, and the pipeline owns its *code*. Any
  Terraform update to the runtime resets the code.
- Ship workflow and Terraform changes together. A workflow that disagrees with the
  runtime (`--service-account` on an Agent Identity runtime) blocks every deploy.
- Keep `deployment_metadata.json` at `null` in git.
- After a deploy, verify: a prompt test, logs including 401s and unlabelled
  warnings, and side effects (objects in the logs bucket).

## Retired

| Resource | Status |
|---|---|
| `projects/sreeai-noorg/locations/us-east4/reasoningEngines/7387508675864166400` (`adk-chatbot`) | Deleted 2026-11-12 (with its sessions) |
| `deploy.env`, `requirements.txt` | Removed (replaced by root `.env` and `pyproject.toml`) |
