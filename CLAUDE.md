# ResolveAI CICD

AI-powered code review tool that analyzes PR diffs against user-defined coding patterns using Anthropic's models, then posts inline review comments back to GitHub PRs.

## How you should act

Act as a criterious system designer that envisions scalability and protection from its IP. Build MVPs as simple as possible and create plans to iterate over. If a proposed option is not followed, explain why.

## Stack

- **Python 3.11+** / **FastAPI** — async API server
- **SQLAlchemy async + aiosqlite** — database (SQLite for MVP, swappable to PostgreSQL)
- **Anthropic API** — two-phase AI review (planning + fix generation)
- **GitHub REST API via httpx** — posting PR reviews with inline comments
- **GitHub Actions** — composite action that extracts diffs and calls our API

## Architecture

```
GitHub Action (on PR)
  → extracts diff via GrantBirki/git-diff-action
  → sends diff + metadata to POST /api/v1/review (X-API-Key auth)
      → loads user patterns from DB
      → Phase 1: Sonnet analyzes diff against patterns → structured issue list (JSON)
      → Phase 2: Sonnet generates concrete code fixes for flagged issues
      → posts PR review with inline comments via GitHub API
```

## Current Implementation (MVP)

### Project Structure
```
app/
  main.py              # FastAPI app, lifespan (auto-creates DB tables)
  config.py            # pydantic-settings (env-based config)
  database.py          # SQLAlchemy async engine + session factory
  models/pattern.py    # ORM: patterns + api_keys tables
  schemas/             # Pydantic request/response models
  auth/api_key.py      # X-API-Key header validation (SHA-256 hashed)
  routers/
    patterns.py        # CRUD /api/v1/patterns/{owner}/{repo}
    review.py          # POST /api/v1/review (orchestrates full flow)
  services/
    prompts.py         # Planner + Executor system prompts
    anthropic_service.py  # plan_review() + generate_fixes()
    github_service.py     # post_review() via httpx
action/action.yml      # Composite GitHub Action
.github/workflows/     # Example user workflow
pre_commit/hook.py     # Local multi-language linter hook
tests/                 # 9 tests, all passing
```

### API Endpoints
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/v1/review | API key | Receive diff, run AI review, post to PR |
| GET | /api/v1/patterns/{owner}/{repo} | API key | Get pattern file |
| PUT | /api/v1/patterns/{owner}/{repo} | API key | Create/update pattern file |
| DELETE | /api/v1/patterns/{owner}/{repo} | API key | Delete pattern file |
| GET | /health | None | Health check |

### Database (SQLite)
- **patterns** — stores claude.md-like files per repo (repository + name unique)
- **api_keys** — static API keys (SHA-256 hashed, scoped per repo)

### Pre-Commit Hook
Runs linters on staged files, writes report to `.resolveai/review.md`. Linters are auto-detected by file extension and only run if the binary is on PATH:

| Language | Linter |
|---|---|
| Python | ruff |
| JavaScript/TypeScript | eslint |
| Go | golangci-lint |
| Rust | cargo clippy |
| Java | checkstyle |
| Ruby | rubocop |
| C/C++ | cppcheck |

### Key Design Decisions
- **github_token passed per-request** from the Action, never stored in our DB
- **"event": "COMMENT"** not "REQUEST_CHANGES" — don't block merges until system is trustworthy
- **httpx over PyGithub** — async-native, lightweight, we only need 2 API calls
- **Sonnet for both phases** in MVP — two-phase interface is built so swapping Opus in is a one-line config change
- **SQLite for MVP** — zero ops; switching to PostgreSQL = change one env var

## Running

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY
uv venv .venv && uv pip install --python .venv -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload
```

## Testing

```bash
ANTHROPIC_API_KEY=test .venv/bin/pytest tests/ -v
```

## Roadmap

### V2 — Production Readiness
- Swap planner model to **claude-opus-4-6** for deeper analysis
- **Pre-commit with optional AI review** (`--ai` flag calls remote API)
- **GitHub App authentication** instead of PATs (finer permissions, better audit)
- **PostgreSQL** for production deployments
- **Rate limiting and usage tracking** per API key
- **API key management CLI/script** (`create_api_key.py`)
- **Multi-tenant isolation** (validate API key scope matches requested repo)
- **Alembic migrations** for schema changes

### V3 — Platform Features
- **Dedicated review page** (web UI for viewing AI reviews outside GitHub)
- **Auto-fix PRs** (bot creates commits with suggested fixes)
- **Feedback loop** (learn from accepted/rejected suggestions)
- **Team-level patterns** (shared across repos in an org)
- **Web UI for pattern management** (CRUD patterns without API calls)
- **Billing and usage metering**

### V4 — Intelligence
- **Context-aware reviews** (fetch full file content, not just diff, for better understanding)
- **PR summary generation** (auto-generate PR descriptions)
- **Cross-PR learning** (detect recurring patterns across reviews)
- **Custom linter rules** generated from patterns
