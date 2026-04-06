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
            └─ Phase 4: Creates review-report.md in the source branch
```

**Two-phase AI review:**
- **Planning** — identifies bugs, pattern violations, security issues, and performance problems
- **Execution** — generates specific code suggestions for each flagged issue

Reviews are posted as `COMMENT` events (not `REQUEST_CHANGES`), so they never block merges.

## Features

- **Pattern-based reviews** — define coding standards per repository (like a CLAUDE.md file) and the AI enforces them
- **Inline PR comments** — issues appear directly on the relevant lines in the PR
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

Edit `.env` and set your `ANTHROPIC_API_KEY`.

### 3. Create an API Key

```bash
.venv/bin/python -m scripts.create_api_key owner/repo
```

This prints a key — save it, it cannot be recovered.

### 4. Start the Server

```bash
.venv/bin/uvicorn app.main:app --reload
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
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./resolveai.db` | Database connection string |
| `PLANNER_MODEL` | No | `claude-sonnet-4-6` | Model for analysis phase |
| `EXECUTOR_MODEL` | No | `claude-sonnet-4-6` | Model for fix generation |
| `DEBUG` | No | `false` | Enable debug logging |

## License

TBD
