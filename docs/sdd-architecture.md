# SDD Architecture for Open SWE

## Goals

- Implement issue-comment mention (`@openswe` / `@open-swe`) as the trigger for SDD runs.
- Add structured SDD lifecycle: **Spec → Plan → Subtasks → Execution → Test → PR → CI autofix**.
- Keep **LangGraph** orchestration while removing hosted/proprietary runtime coupling.
- Support **GitHub.com + GitHub Enterprise**, **Slack**, **PostgreSQL/SQLite**, and sandbox types:
  - `SANDBOX_TYPE=docker-container`
  - `SANDBOX_TYPE=k8s-pod`

## Architectural Changes

### 1) Persistence Layer (SQL, Postgres/SQLite)

- Add a storage module with a SQL backend selected by `DATABASE_URL`.
  - SQLite DSN supports relative and absolute paths (`sqlite:///relative.db`, `sqlite:////abs/path.db`).
  - PostgreSQL DSN uses `postgresql+psycopg://...`.
- Persist SDD entities:
  - `sdd_specs`
  - `sdd_plans`
  - `sdd_subtasks`
  - `sdd_runs`
  - `sdd_events`
- Keep thread metadata usage for compatibility, but move SDD state of record to SQL.

### 2) SDD Orchestration in Agent Pipeline

- Extend GitHub issue flow:
  1. Parse issue + comments into strict `SDD_SPEC`.
  2. Generate strict `SDD_PLAN`.
  3. Generate strict `SDD_SUBTASKS`.
  4. Execute subtasks in sandbox.
  5. Run tests and open/update PR.
- Persist each artifact and transition state in SQL.
- Add deterministic run states (`queued`, `planning`, `executing`, `testing`, `pr_opened`, `ci_fixing`, `done`, `failed`).

### 3) Sandbox Provider Refactor

- Replace managed external providers with local/self-hosted providers:
  - Docker container sandbox backend.
  - Kubernetes pod sandbox backend.
- Keep `local` backend for local development.
- Remove Modal/Daytona/Runloop/LangSmith sandbox runtime paths and docs references.

### 4) Trigger and Integration Surface

- GitHub webhook remains primary for coding runs, triggered by mention in issue thread comments.
- Keep PR review/comment follow-up behavior.
- Remove Linear webhook/tooling/config paths.
- Keep Slack webhook and outbound Slack notification hooks for key SDD state transitions.

### 5) CI Observation + Auto-Fix

- Add CI monitor logic for agent-opened PRs:
  - Detect failure status from GitHub checks.
  - Queue bounded fix rounds (`max_ci_fix_rounds=2` configurable).
  - Record rounds in SQL run state and post status updates to Slack/GitHub.

### 6) Model and Observability

- Restrict model provider configuration to OpenAI model IDs.
- Remove cross-provider fallback routing.
- Remove LangSmith trace URL dependencies from user-facing responses.
- Keep logging; add OpenTelemetry/Prometheus-compatible metrics hooks (counter/timer labels by source, run state, CI round).

### 7) Deployment Model

- Host mode: `uvicorn agent.webapp:app` or `langgraph dev`.
- Container mode:
  - Application container.
  - Optional PostgreSQL service.
  - Optional OTEL collector / Prometheus scrape endpoint.

## Migration Strategy

1. Add SDD schema + storage adapter.
2. Introduce strict format serializers/validators.
3. Wire SDD generation and persistence into GitHub issue flow.
4. Add CI-fix loop.
5. Remove Linear and managed sandbox providers.
6. Update docs/env/deployment manifests.
7. Re-run lint/tests and stabilize.
