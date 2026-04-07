# ResolveAI CICD

AI-powered code review tool that integrates with GitHub Actions. When a pull request is opened, it extracts the diff, analyzes it against your repository's coding patterns using Anthropic's Claude, and posts inline review comments directly on the PR. **When no PR exists, it can create one automatically with a full markdown review report.**

## How It Works

### Standard Flow (PR Already Exists)

```
PR opened/updated
  └─ GitHub Action extracts diff
       └─ Sends diff to ResolveAI API (POST /api/v1/review)
            ├─ Loads your coding patterns from the database
            ├─ Phase 1: Claude analyzes diff → structured list of issues
            ├─ Phase 2: Claude generates concrete code fixes
            └─ Posts review with inline comments to the PR via GitHub API
```

### Auto-Review Flow (No PR Exists)

```
Commit pushed to a branch without a PR
  └─ GitHub Action extracts diff
       └─ Sends diff to ResolveAI API (POST /api/v1/auto-review, create_pr=true)
            ├─ Phase 0: API creates a new PR automatically
            ├─ Loads your coding patterns from the database
            ├─ Phase 1: Claude analyzes diff → structured list of issues
            ├─ Phase 2: Claude generates concrete code fixes
            ├─ Phase 3: Posts review with inline comments to the new PR
            ├─ Phase 3.5: Posts the full diff as a collapsible comment in the PR conversation tab
            └─ Phase 4: Creates review-report.md in the source branch
```

**Two-phase AI review:**
- **Planning** — identifies bugs, pattern violations, security issues, and performance problems
- **Execution** — generates specific code suggestions for each flagged issue

Reviews are posted as `COMMENT` events (not `REQUEST_CHANGES`), so they never block merges.

## Features

- **Pattern-based reviews** — define coding standards per repository (like a CLAUDE.md file) and the AI enforces them
- **Inline PR comments** — issues appear directly on the relevant lines in the PR
- **Diff in conversation tab** — the full git diff is posted as a collapsible comment in the PR conversation, so reviewers see the complete changeset without switching tabs
- **Auto-create PRs** — when no PR exists, the API can create one automatically with inline comments + a `review-report.md` file
- **Markdown review reports** — full analysis report committed to the source branch
- **Multi-language pre-commit hook** — local linting for Python, JS/TS, Go, Rust, Java, Ruby, C/C++
- **Works with private repos** — the GitHub Action runs inside the repo context; the API never clones or accesses your code directly
- **API key auth** — keys are SHA-256 hashed, scoped per repository

## Stack

- Python 3.11+ / FastAPI
- SQLAlchemy async + SQLite (swappable to PostgreSQL)
- Anthropic API (Claude Sonnet, with Opus swap for planning phase)
- GitHub REST API via httpx
- GitHub Actions (composite action)

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (or pip)
- An [Anthropic API key](https://console.anthropic.com/)
- [GitHub CLI (`gh`)](https://cli.github.com/) — required for local testing scripts (`scripts/test_local_review.py`). Install with your package manager:
  ```bash
  # Arch / CachyOS
  sudo pacman -S github-cli

  # Ubuntu / Debian
  sudo apt install gh

  # macOS
  brew install gh
  ```
  Then authenticate: `gh auth login`

### 1. Install

```bash
git clone https://github.com/YOUR_ORG/resolveai-cicd.git
cd resolveai-cicd
uv venv .venv
uv pip install --python .venv -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
```

> **Security:** Do not put `ANTHROPIC_API_KEY` in `.env`. Pass it inline when starting the server or store it in GitHub secrets — never commit it to the repository.

Start the server with the key inline:

```bash
ANTHROPIC_API_KEY=sk-ant-... .venv/bin/uvicorn app.main:app --reload
```

Or export it in your shell session:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/uvicorn app.main:app --reload
```

For GitHub Actions deployments, add `ANTHROPIC_API_KEY` as a repository secret and inject it via the workflow environment.

### 3. Create an API Key

```bash
.venv/bin/python -m scripts.create_api_key owner/repo
```

This prints a key — save it, it cannot be recovered.

### 4. Start the Server

```bash
ANTHROPIC_API_KEY=sk-ant-... .venv/bin/uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

## Testing the API

### Health Check

```bash
curl http://localhost:8000/health
```

### Create a Coding Pattern

```bash
curl -X PUT http://localhost:8000/api/v1/patterns/owner/repo \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"content": "# Patterns\n- Use snake_case\n- Add type hints to all functions"}'
```

### Read a Pattern

```bash
curl http://localhost:8000/api/v1/patterns/owner/repo \
  -H "X-API-Key: YOUR_KEY"
```

### Submit a Review

This calls Anthropic to analyze the diff and posts the review to a GitHub PR:

```bash
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "repository": "owner/repo",
    "pr_number": 1,
    "diff_raw": "diff --git a/main.py b/main.py\n--- a/main.py\n+++ b/main.py\n@@ -1,3 +1,5 @@\n+password = \"admin123\"\n+\n def hello():\n-    print(\"hi\")\n+    print(\"hello world\")",
    "base_ref": "main",
    "head_ref": "feature/test",
    "github_token": "ghp_YOUR_GITHUB_PAT",
    "commit_sha": "abc1234"
  }'
```

**Note:** The `github_token` needs `pull-requests: write` scope and the PR must exist. To test just the AI analysis without posting to GitHub, use a fake token — Anthropic will process the diff and you'll see the analysis in the error response before the GitHub step fails.

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/v1/review` | API key | Receive diff, run AI review, post inline comments to existing PR |
| `POST` | `/api/v1/auto-review` | API key | Receive diff, auto-create PR if needed, post inline comments + `review-report.md` |
| `GET` | `/api/v1/patterns/{owner}/{repo}` | API key | Get coding pattern file |
| `PUT` | `/api/v1/patterns/{owner}/{repo}` | API key | Create or update pattern file |
| `DELETE` | `/api/v1/patterns/{owner}/{repo}` | API key | Delete pattern file |
| `GET` | `/health` | None | Health check |

## GitHub Action Integration

Add the action to any repository to get AI reviews on every PR.

### 1. Set Repository Secrets

- `RESOLVEAI_API_URL` — your deployed API URL
- `RESOLVEAI_API_KEY` — the API key for this repo

### 2. Create the Workflow

#### Standard — Review Existing PRs

Create `.github/workflows/resolveai-review.yml`:

```yaml
name: ResolveAI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: YOUR_ORG/resolveai-cicd/action@main
        with:
          api_url: ${{ secrets.RESOLVEAI_API_URL }}
          api_key: ${{ secrets.RESOLVEAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

#### Auto-Create PRs — When No PR Exists

```yaml
name: ResolveAI Auto Review

on:
  push:
    branches: ['**']

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-review:
    if: ${{ !github.event.pull_request }}
    runs-on: ubuntu-latest
    steps:
      - uses: YOUR_ORG/resolveai-cicd/action@main
        with:
          api_url: ${{ secrets.RESOLVEAI_API_URL }}
          api_key: ${{ secrets.RESOLVEAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          create_pr: true
          pr_title: 'ResolveAI Auto-Review — ${{ github.ref_name }}'
          pr_body: 'Automatically created by ResolveAI for code review.'
```

### Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api_url` | Yes | — | ResolveAI API URL |
| `api_key` | Yes | — | API key |
| `github_token` | No | `${{ github.token }}` | GitHub token |
| `create_pr` | No | `false` | Auto-create PR when none exists |
| `pr_title` | No | `ResolveAI Auto-Review` | Title for auto-created PR |
| `pr_body` | No | _default message_ | Body for auto-created PR |

## Integrating Other Repositories

Any repository can be connected to the same deployed API instance. Repeat these steps for each new repo:

### 1. Create an API key for the repo

```bash
# On the machine running the API (or via railway run / fly ssh)
.venv/bin/python -m scripts.create_api_key owner/new-repo
```

Save the printed raw key — it cannot be recovered.

> **Note:** API key scope is not enforced yet (V2 roadmap). A single key technically works for all repos, but creating one per repo is recommended for future isolation and revocation.

### 2. Add the workflow to the target repo

Create `.github/workflows/resolveai-review.yml` in the target repository's `main` branch. Use the inlined version below (avoids a cross-repo dependency on the `resolveAI_cicd` action):

```yaml
name: ResolveAI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: GrantBirki/git-diff-action@v2
        id: diff
        with:
          raw_diff_file_output: diff.txt
          file_output_only: "true"

      - name: Send diff to ResolveAI
        env:
          API_URL: ${{ secrets.RESOLVEAI_API_URL }}
          API_KEY: ${{ secrets.RESOLVEAI_API_KEY }}
          GITHUB_TOKEN_INPUT: ${{ secrets.GITHUB_TOKEN }}
          REPOSITORY: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          BASE_REF: ${{ github.event.pull_request.base.ref }}
          HEAD_REF: ${{ github.event.pull_request.head.ref }}
          COMMIT_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          DIFF_CONTENT=$(cat diff.txt)
          if [ -z "$DIFF_CONTENT" ]; then
            echo "No diff found, skipping review"
            exit 0
          fi

          PAYLOAD=$(jq -n \
            --arg repo "$REPOSITORY" \
            --argjson pr "$PR_NUMBER" \
            --arg diff "$DIFF_CONTENT" \
            --arg base "$BASE_REF" \
            --arg head "$HEAD_REF" \
            --arg token "$GITHUB_TOKEN_INPUT" \
            --arg sha "$COMMIT_SHA" \
            '{repository:$repo,pr_number:$pr,diff_raw:$diff,base_ref:$base,head_ref:$head,github_token:$token,commit_sha:$sha}')

          HTTP_STATUS=$(curl -s -o /tmp/resolveai_response.json -w "%{http_code}" \
            -X POST "${API_URL}/api/v1/review" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: ${API_KEY}" \
            -d "$PAYLOAD")

          echo "ResolveAI API response (HTTP $HTTP_STATUS):"
          cat /tmp/resolveai_response.json

          if [ "$HTTP_STATUS" -lt 200 ] || [ "$HTTP_STATUS" -ge 300 ]; then
            exit 1
          fi
```

### 3. Set repository secrets

In the target repo go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `RESOLVEAI_API_URL` | Your deployed API URL (no trailing slash) |
| `RESOLVEAI_API_KEY` | Raw key from step 1 |

`GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.

### 4. (Optional) Add repo-specific coding patterns

```bash
curl -X PUT https://<your-api>/api/v1/patterns/owner/new-repo \
  -H "X-API-Key: <key>" \
  -H "Content-Type: application/json" \
  -d '{"content": "- Always use async/await\n- No hardcoded secrets\n- All public functions need docstrings"}'
```

The AI will enforce these rules on every PR in that repository.

## Pre-Commit Hook

Local linting hook that runs on staged files and writes a report to `.resolveai/review.md`. Each linter only runs if its binary is available on PATH.

| Language | Linter |
|---|---|
| Python | ruff |
| JavaScript/TypeScript | eslint |
| Go | golangci-lint |
| Rust | cargo clippy |
| Java | checkstyle |
| Ruby | rubocop |
| C/C++ | cppcheck |

### Install via pre-commit

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/YOUR_ORG/resolveai-cicd
    rev: main
    hooks:
      - id: resolveai-review
```

## Developer Scripts

All scripts live in `scripts/` and are meant to be run with the server already running locally (`uvicorn app.main:app --reload`).

### `scripts/full_review_demo.py`

End-to-end demo that creates a PR, runs the full AI review, posts inline comments, and posts the diff as a collapsible conversation comment.

```bash
GITHUB_TOKEN=<pat> .venv/bin/python scripts/full_review_demo.py
```

Sets `create_pr=true`, so it creates a new branch and PR on `mnsgrosa/ResolveAI-demos` with a Go auth handler containing intentional security issues. After it completes, open the PR URL printed in the output to see:
- Inline comments on flagged lines (Files changed tab)
- Collapsible diff comment in the Conversation tab (one `<details>` block per file)
- `review-report.md` committed to the source branch

The `GITHUB_TOKEN` must have `contents: write` and `pull-requests: write` permissions on the target repo.

### `scripts/test_diff_comment.py`

Unit-level test for `post_diff_comment` only — no server needed, no AI calls, no full review. Useful for iterating on the diff comment formatting in isolation.

```bash
GITHUB_TOKEN=<pat> .venv/bin/python scripts/test_diff_comment.py
```

Posts a two-file sample diff as a conversation comment to PR #1 of `mnsgrosa/ResolveAI-demos`. Edit `REPOSITORY` and `PR_NUMBER` at the top of the file to target a different PR.

### `scripts/request_review.py`

Sends a hardcoded Go diff to `POST /api/v1/review` against an existing PR. Useful for testing the standard review flow without auto-PR creation.

```bash
.venv/bin/python scripts/request_review.py
```

Edit `API_KEY`, `GITHUB_TOKEN`, and `REQUEST_BODY` fields at the top of the file before running.

### `scripts/test_local_review.py`

Sends a **real PR diff** to the local API for end-to-end testing without deploying anything. Fetches the diff, commit SHA, and refs directly from GitHub via the `gh` CLI, then POSTs to the local server.

**Requires:** local API running + `gh` CLI authenticated.

```bash
.venv/bin/python -m scripts.test_local_review owner/repo <pr_number> --api-key <key>

# Example
.venv/bin/python -m scripts.test_local_review mnsgrosa/ResolveAI-demos 3 --api-key <key>

# Point to a remote deployment instead of localhost
.venv/bin/python -m scripts.test_local_review owner/repo 3 --api-key <key> --api-url https://your-api.example.com
```

The script prints the review ID, number of inline comments posted, and the AI summary.

### `scripts/create_api_key.py`

Creates a new API key scoped to a repository and stores it (hashed) in the database.

```bash
.venv/bin/python -m scripts.create_api_key owner/repo
```

### `scripts/send_go_pattern.py`

Uploads a Go coding pattern file to the patterns API for a given repository.

```bash
.venv/bin/python scripts/send_go_pattern.py
```

## Running Tests

```bash
ANTHROPIC_API_KEY=test .venv/bin/pytest tests/ -v
```

## Deployment

### Docker

```bash
docker build -t resolveai-cicd .
docker run -p 8000:8000 --env-file .env resolveai-cicd
```

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key — pass inline or via shell export, never commit to `.env` |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./resolveai.db` | Database connection string |
| `PLANNER_MODEL` | No | `claude-sonnet-4-6` | Model for analysis phase |
| `EXECUTOR_MODEL` | No | `claude-sonnet-4-6` | Model for fix generation |
| `DEBUG` | No | `false` | Enable debug logging |

## License

TBD
