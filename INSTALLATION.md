
# Installation Guide

This guide walks you through setting up Open SWE end-to-end: local development, GitHub App creation, PostgreSQL-backed runtime storage, Slack/GitHub webhooks, and production deployment.

> **The steps are ordered to avoid forward references.** Each step only depends on things you've already completed.

## Prerequisites

- **Python 3.11 – 3.13** (3.14 is not yet supported due to dependency constraints)
- [uv](https://docs.astral.sh/uv/) package manager
- [LangGraph CLI](https://langchain-ai.github.io/langgraph/cloud/reference/cli/)
- [ngrok](https://ngrok.com/) (for local development — exposes webhook endpoints to the internet)

## 1. Clone and install

```bash
git clone https://github.com/langchain-ai/open-swe.git
cd open-swe
uv venv
source .venv/bin/activate
uv sync --all-extras
```

## 2. Start ngrok

You'll need the ngrok URL in subsequent steps when configuring webhooks, so start it first.

```bash
ngrok http 2024 --url https://some-url-you-configure.ngrok.dev
```

You don't need to pass the `--url` flag, however doing so will use the same subdomain each time you startup the server. Without this, you'll need to update the webhook URL in GitHub and Slack every time you restart your server for local development.

Copy the HTTPS URL you set, or if you didn't pass `--url`, the one ngrok gives you. You'll paste this into the webhook settings in steps 3 and 5.

> Keep this terminal open — ngrok needs to stay running during local development. Use a second terminal for the rest of the steps.

## 3. Create a GitHub App

Open SWE authenticates as a [GitHub App](https://docs.github.com/en/apps/creating-github-apps) to clone repos, push branches, and open PRs.

### 3a. Create the app

1. Go to **GitHub Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in:
    - **App name**: `open-swe` (or your preferred name)
    - **Homepage URL**: This can be any valid URL — it's only shown on the GitHub Marketplace page (which you won't be using). Use something like `https://github.com/langchain-ai/open-swe`
    - **Webhook URL**: `https://<your-ngrok-url>/webhooks/github` — use the ngrok URL from step 2
    - **Webhook secret**: generate one and save it — you'll need it later as `GITHUB_WEBHOOK_SECRET`:
      ```bash
      openssl rand -hex 32
      ```
3. Set permissions:
   - **Repository permissions**:
     - Contents: Read & write
     - Pull requests: Read & write
     - Issues: Read & write
     - Metadata: Read-only
4. Under **Subscribe to events**, enable:
   - `Issue comment`
    - `Check suite`
    - `Pull request`
    - `Pull request review`
    - `Pull request review comment`
5. Click **Create GitHub App**

### 3b. Collect credentials

After creating the app:

1. **App ID** — shown at the top of the app's settings page. Save this as `GITHUB_APP_ID`.
2. **Private key** — scroll down to **Private keys** → click **Generate a private key**. A `.pem` file will download. Save its contents as `GITHUB_APP_PRIVATE_KEY`.

### 3c. Install the app on your repositories

1. From your app's settings page, click **Install App** in the sidebar
2. Select your org or personal account
3. Choose which repositories Open SWE should have access to
4. Click **Install**
5. After installation, look at the URL in your browser — it will look like:
   ```
   https://github.com/settings/installations/12345678
   ```
   or for an org:
   ```
   https://github.com/organizations/YOUR-ORG/settings/installations/12345678
   ```
   The number at the end (`12345678`) is your **Installation ID**. Save this as `GITHUB_APP_INSTALLATION_ID`.

## 4. Set up runtime storage and sandboxing

Open SWE persists SDD artifacts and run metadata in SQL storage selected by `DATABASE_URL`, and runs tasks in self-hosted sandbox backends selected by `SANDBOX_TYPE`.

### 4a. Start PostgreSQL and Langfuse (recommended)

The easiest path is Docker Compose:

```bash
docker compose up -d postgres langfuse-web langfuse-worker clickhouse minio redis
```

Use this connection string:

```bash
DATABASE_URL="postgresql+psycopg://open_swe:open_swe@localhost:5432/open_swe"
```

SQLite also works for local development:

```bash
DATABASE_URL="sqlite:///open_swe.db"
```

### 4b. Choose a sandbox backend

Supported values:

- `docker-container` (default) — requires Docker plus a `SANDBOX_IMAGE`
- `k8s-pod` — requires `kubectl` access plus a `SANDBOX_IMAGE`
- `local` — development only; runs directly on the host

To build a sandbox image locally:

```bash
docker build -t my-open-swe-sandbox:latest .
```

## 5. Set up triggers

Open SWE can be triggered from GitHub and/or Slack.

### GitHub

GitHub triggering works automatically once your GitHub App is set up (step 3). Users can:
- Tag `@openswe` in issue titles or bodies to start a task
- Tag `@openswe` in issue comments for follow-up instructions
- Tag `@openswe` in PR review comments to have it address review feedback
- Failed `check_suite` events can trigger bounded CI autofix retries for tracked PR runs

To control which GitHub users can trigger the agent, add them to the `GITHUB_USER_EMAIL_MAP` in `agent/utils/github_user_email_map.py`:

```python
GITHUB_USER_EMAIL_MAP = {
    "their-github-username": "their-email@example.com",
}
```

You should also configure which GitHub organizations and/or repositories the agent is allowed to operate on. You can specify allowed orgs, specific `owner/repo` pairs, or both:

```bash
# Allow all repos in these orgs
ALLOWED_GITHUB_ORGS="langchain-ai,anthropics"

# Allow specific repos (owner/repo format)
ALLOWED_GITHUB_REPOS="some-user/their-repo,another-org/specific-repo"
```

A webhook is accepted if the repo's org is in `ALLOWED_GITHUB_ORGS` **or** the `owner/repo` is in `ALLOWED_GITHUB_REPOS`. If both are empty, all repos are allowed.

### Slack (optional)

**Create a Slack App:**

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From a manifest**
2. Copy the manifest below, replacing `<your-ngrok-url>` with the ngrok URL from step 2

<details>
<summary>Slack App Manifest</summary>

```json
{
    "display_information": {
        "name": "Open SWE",
        "description": "Enables Open SWE to interact with your workspace",
        "background_color": "#000000"
    },
    "features": {
        "app_home": {
            "home_tab_enabled": false,
            "messages_tab_enabled": true,
            "messages_tab_read_only_enabled": false
        },
        "bot_user": {
            "display_name": "Open SWE",
            "always_online": true
        }
    },
    "oauth_config": {
        "scopes": {
            "bot": [
                "reactions:write",
                "app_mentions:read",
                "channels:history",
                "channels:read",
                "chat:write",
                "groups:history",
                "groups:read",
                "im:history",
                "im:read",
                "im:write",
                "mpim:history",
                "mpim:read",
                "team:read",
                "users:read",
                "users:read.email"
            ]
        }
    },
    "settings": {
        "event_subscriptions": {
            "request_url": "https://<your-ngrok-url>/webhooks/slack",
            "bot_events": [
                "app_mention",
                "message.im",
                "message.mpim"
            ]
        },
        "org_deploy_enabled": false,
        "socket_mode_enabled": false,
        "token_rotation_enabled": false
    }
}
```

</details>

3. Install the app to your workspace and copy the **Bot User OAuth Token** (`xoxb-...`)

**Credentials you'll need:**

- `SLACK_BOT_TOKEN`: the Bot User OAuth Token (`xoxb-...`)
- `SLACK_SIGNING_SECRET`: found under **Basic Information → App Credentials**
- `SLACK_BOT_USER_ID`: the bot's user ID (find it in Slack by clicking the bot's profile)
- `SLACK_BOT_USERNAME`: the bot's display name (e.g. `open-swe`)

**Default repo:**

Slack messages are routed to the default repo (`DEFAULT_REPO_OWNER`/`DEFAULT_REPO_NAME` — see step 6) unless the user specifies one with `repo:owner/name` in their message.

## 6. Environment variables

Create a `.env` file in the project root. Below is the full list — only fill in the sections relevant to the triggers you configured.

```bash
# === LLM ===
OPENAI_API_KEY=""
LLM_MODEL_ID="openai:gpt-5.5"

# === GitHub App (required) ===
GITHUB_APP_ID=""                       # From step 3b
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
"
GITHUB_APP_INSTALLATION_ID=""          # From step 3c

# === GitHub Webhook (required) ===
GITHUB_WEBHOOK_SECRET=""               # The secret you generated in step 3a

# === Repo Allowlist (optional) ===
# Comma-separated list of GitHub orgs the agent is allowed to operate on.
# Leave empty to allow all orgs.
ALLOWED_GITHUB_ORGS=""                 # e.g. "my-org,my-other-org"
# Comma-separated list of specific owner/repo pairs the agent is allowed to operate on.
# A repo is allowed if its org is in ALLOWED_GITHUB_ORGS OR its owner/repo is in ALLOWED_GITHUB_REPOS.
# Leave both empty to allow all repos.
ALLOWED_GITHUB_REPOS=""                # e.g. "some-user/their-repo,another-org/specific-repo"

# === Default Repository ===
# Used across all triggers when no repo is specified.
DEFAULT_REPO_OWNER=""                  # Default GitHub org (e.g. "my-org")
DEFAULT_REPO_NAME=""                   # Default GitHub repo (e.g. "my-repo")

# === Slack (if using Slack trigger) ===
SLACK_BOT_TOKEN=""                     # From step 5
SLACK_BOT_USER_ID=""
SLACK_BOT_USERNAME=""
SLACK_SIGNING_SECRET=""

# === Exa (optional — enables web search tool) ===
EXA_API_KEY=""                         # From https://dashboard.exa.ai

# === Runtime storage ===
DATABASE_URL="postgresql+psycopg://open_swe:open_swe@localhost:5432/open_swe"

# === Sandbox ===
SANDBOX_TYPE="docker-container"        # docker-container | k8s-pod | local
SANDBOX_IMAGE="my-open-swe-sandbox:latest"
SANDBOX_K8S_NAMESPACE="default"        # optional for k8s-pod

# === CI auto-fix ===
MAX_CI_FIX_ROUNDS="2"

# === Observability (optional) ===
OTEL_TRACES_ENABLED="true"
OTEL_SERVICE_NAME="open-swe"
OTEL_EXPORTER_OTLP_ENDPOINT=""         # e.g. https://collector.example/v1/traces
OTEL_EXPORTER_OTLP_HEADERS=""          # e.g. "Authorization=Bearer token"
LANGFUSE_ENABLED="true"
LANGFUSE_PUBLIC_KEY="pk-lf-local"
LANGFUSE_SECRET_KEY="sk-lf-local"
LANGFUSE_HOST="http://localhost:3000"
CLICKHOUSE_CLUSTER_ENABLED="false"      # required for local single-node ClickHouse

# === Token Encryption ===
TOKEN_ENCRYPTION_KEY=""                # Generate with: openssl rand -base64 32
                                       # Supports key rotation: see "Rotating TOKEN_ENCRYPTION_KEY" below
```

If you're using the bundled Docker Compose Langfuse stack, the defaults above work out-of-the-box.
Open `http://localhost:3000` and sign in with:

- Email: `admin@open-swe.local`
- Password: `open-swe-local-password`

⚠️ These defaults are for local development only. For production, override these values and rotate all secrets before exposing the stack.

### Rotating TOKEN_ENCRYPTION_KEY

`TOKEN_ENCRYPTION_KEY` accepts either a single Fernet key or a comma- or
newline-separated **ordered list of keys, most-recent-first**. New writes always
encrypt under the first key; reads try every key in order. To rotate without
invalidating already-stored GitHub tokens:

1. Generate a new key: `openssl rand -base64 32`.
2. Prepend it to `TOKEN_ENCRYPTION_KEY`, keeping the old key second:
   ```
   TOKEN_ENCRYPTION_KEY="<new_key>,<old_key>"
   ```
   Restart the server. New encryptions use `<new_key>`; existing ciphertexts
   still decrypt against `<old_key>`.
3. Let active threads cycle (each fresh OAuth flow re-encrypts under the new
   key). After every active thread has re-authed, drop the old key:
   ```
   TOKEN_ENCRYPTION_KEY="<new_key>"
   ```
   Any thread still holding ciphertext under `<old_key>` will fail to decrypt
   and the user will be re-prompted to authenticate — same UX as if the thread
   had never authed.

## 7. Start the server

Make sure ngrok is still running from step 2, then start the LangGraph server in a second terminal:

```bash
uv run langgraph dev --no-browser
```

The server runs on `http://localhost:2024` with these endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /webhooks/github` | GitHub issue/PR/comment webhooks |
| `POST /webhooks/slack` | Slack event webhooks |
| `GET /webhooks/slack` | Slack webhook verification |
| `GET /health` | Health check |
| `GET /metrics` | Prometheus metrics |

## 8. Verify it works

### GitHub

1. Go to any issue in a repository where the app is installed
2. Create or comment on an issue with: `@openswe what files are in this repo?`
3. You should see:
    - A 👀 reaction on your comment within a few seconds
    - SDD artifacts and run metadata written to your configured database
    - The agent replies with a comment on the issue

### Slack

1. In any channel where the bot is invited, start a thread
2. Mention the bot: `@open-swe what's in the repo?`
3. You should see:
   - An 👀 reaction on your message
   - A reply in the thread with the agent's response

## 9. Production deployment

For production, deploy the agent behind your preferred process manager or container platform:

1. Push your code to a GitHub repository
2. Build and publish the application image plus your configured `SANDBOX_IMAGE`
3. Provision PostgreSQL and set all environment variables from step 6
4. Run `docker compose up -d` (or translate the same services to Kubernetes)
5. Update your webhook URLs (Slack, GitHub App) to point to your production URL

The `langgraph.json` at the project root already defines the graph entry point and HTTP app:

```json
{
  "graphs": {
    "agent": "agent.server:get_agent"
  },
  "http": {
    "app": "agent.webapp:app"
  }
}
```

## Troubleshooting

### Webhook not receiving events

- Verify ngrok is running and the URL matches what's configured in GitHub/Slack
- Check the ngrok web inspector at `http://localhost:4040` for incoming requests
- Ensure you enabled the correct event types (`app_mention` for Slack, and the subscribed GitHub issue / PR / check events for GitHub)
- **Webhook secrets are required** — if `GITHUB_WEBHOOK_SECRET` or `SLACK_SIGNING_SECRET` is not set, requests to that endpoint will be rejected with 401

### GitHub authentication errors

- Verify `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, and `GITHUB_APP_INSTALLATION_ID` are set correctly
- Ensure the GitHub App is installed on the target repositories
- Check that the private key includes the full `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines

### Sandbox creation failures

- Verify `SANDBOX_TYPE` is one of `docker-container`, `k8s-pod`, or `local`
- For `docker-container`, confirm Docker is installed and the configured `SANDBOX_IMAGE` exists locally
- For `k8s-pod`, confirm `kubectl` can create pods in the target cluster/namespace and the sandbox image is pullable there
- If using PostgreSQL, verify `DATABASE_URL` points at a reachable database

### Agent not responding to comments

- For GitHub: ensure the comment or issue contains `@openswe` (case-insensitive), and the commenter's GitHub username is in `GITHUB_USER_EMAIL_MAP`
- For Slack: ensure the bot is invited to the channel and the message is an `@mention`
- Check server logs for webhook processing errors

### Token encryption errors

- Ensure `TOKEN_ENCRYPTION_KEY` is set (generate with `openssl rand -base64 32`)
- The key must be a valid 32-byte Fernet-compatible base64 string
- For key rotation, `TOKEN_ENCRYPTION_KEY` may be a comma- or newline-separated
  list of keys (most-recent-first). See "Rotating TOKEN_ENCRYPTION_KEY" above.
