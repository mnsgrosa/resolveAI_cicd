from unittest.mock import AsyncMock, patch

import pytest

from app.services.anthropic_service import ReviewIssue, ReviewPlan
from tests.conftest import TEST_API_KEY, TEST_REPO

SAMPLE_DIFF = """\
diff --git a/app/main.py b/app/main.py
index 1234567..abcdefg 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,5 +1,8 @@
+import os
+
 from fastapi import FastAPI

+password = "hardcoded_secret"  # BAD
+
 app = FastAPI()
"""

MOCK_PLAN = ReviewPlan({
    "summary": "Found a hardcoded secret in main.py.",
    "issues": [
        {
            "file": "app/main.py",
            "line_start": 4,
            "line_end": 4,
            "severity": "critical",
            "description": "Hardcoded password detected",
            "needs_fix": True,
        }
    ],
})

MOCK_PR_INFO = {
    "number": 42,
    "html_url": "https://github.com/test-owner/test-repo/pull/42",
    "id": "999",
}


@pytest.mark.asyncio
async def test_auto_review_with_existing_pr(client):
    """Auto-review with an existing PR number behaves like /review."""
    with (
        patch(
            "app.routers.auto_review.plan_review",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.auto_review.generate_fixes",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.auto_review.post_review",
            new_callable=AsyncMock,
            return_value="42",
        ),
        patch(
            "app.routers.auto_review.create_or_update_file",
            new_callable=AsyncMock,
        ) as mock_create_file,
    ):
        resp = await client.post(
            "/api/v1/auto-review",
            json={
                "repository": TEST_REPO,
                "pr_number": 1,
                "diff_raw": SAMPLE_DIFF,
                "base_ref": "main",
                "head_ref": "feature/test",
                "github_token": "ghp_fake",
                "commit_sha": "abc1234",
            },
            headers={"X-API-Key": TEST_API_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["review_id"] == "42"
    assert data["pr_number"] == 1
    assert data["report_file_path"] is None  # not created when PR already exists
    mock_create_file.assert_not_called()


@pytest.mark.asyncio
async def test_auto_review_create_pr_new(client):
    """Auto-review with create_pr=True and no pr_number creates a PR + report."""
    with (
        patch(
            "app.routers.auto_review.get_branch_sha",
            new_callable=AsyncMock,
            return_value="base-sha-abc",
        ),
        patch(
            "app.routers.auto_review.create_branch",
            new_callable=AsyncMock,
        ),
        patch(
            "app.routers.auto_review.create_pull_request",
            new_callable=AsyncMock,
            return_value=MOCK_PR_INFO,
        ),
        patch(
            "app.routers.auto_review.plan_review",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.auto_review.generate_fixes",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.auto_review.post_review",
            new_callable=AsyncMock,
            return_value="100",
        ),
        patch(
            "app.routers.auto_review.create_or_update_file",
            new_callable=AsyncMock,
            return_value="file-sha-xyz",
        ),
    ):
        resp = await client.post(
            "/api/v1/auto-review",
            json={
                "repository": TEST_REPO,
                "diff_raw": SAMPLE_DIFF,
                "base_ref": "main",
                "head_ref": "feature/test",
                "github_token": "ghp_fake",
                "commit_sha": "abc1234",
                "create_pr": True,
                "pr_title": "Auto Review PR",
                "pr_body": "Please review this PR",
            },
            headers={"X-API-Key": TEST_API_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["pr_number"] == 42
    assert "pull/42" in data["pr_url"]
    assert data["report_file_path"] == "review-report.md"


@pytest.mark.asyncio
async def test_auto_review_no_pr_number_and_create_pr_false(client):
    """Should return 400 when pr_number is None and create_pr is False."""
    resp = await client.post(
        "/api/v1/auto-review",
        json={
            "repository": TEST_REPO,
            "diff_raw": SAMPLE_DIFF,
            "base_ref": "main",
            "head_ref": "feature/test",
            "github_token": "ghp_fake",
            "commit_sha": "abc1234",
            "create_pr": False,
        },
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_auto_review_pr_creation_fails(client):
    """Should return 502 when PR creation fails."""
    with (
        patch(
            "app.routers.auto_review.get_branch_sha",
            new_callable=AsyncMock,
            return_value="base-sha-abc",
        ),
        patch(
            "app.routers.auto_review.create_branch",
            new_callable=AsyncMock,
        ),
        patch(
            "app.routers.auto_review.create_pull_request",
            new_callable=AsyncMock,
            side_effect=Exception("Branch not found"),
        ),
    ):
        resp = await client.post(
            "/api/v1/auto-review",
            json={
                "repository": TEST_REPO,
                "diff_raw": SAMPLE_DIFF,
                "base_ref": "main",
                "head_ref": "feature/test",
                "github_token": "ghp_fake",
                "commit_sha": "abc1234",
                "create_pr": True,
            },
            headers={"X-API-Key": TEST_API_KEY},
        )
    assert resp.status_code == 502
    assert "Branch not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auto_review_anthropic_planning_fails(client):
    """Should return 502 when planning fails, even after PR is created."""
    with (
        patch(
            "app.routers.auto_review.get_branch_sha",
            new_callable=AsyncMock,
            return_value="base-sha-abc",
        ),
        patch(
            "app.routers.auto_review.create_branch",
            new_callable=AsyncMock,
        ),
        patch(
            "app.routers.auto_review.create_pull_request",
            new_callable=AsyncMock,
            return_value=MOCK_PR_INFO,
        ),
        patch(
            "app.routers.auto_review.plan_review",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ),
    ):
        resp = await client.post(
            "/api/v1/auto-review",
            json={
                "repository": TEST_REPO,
                "diff_raw": SAMPLE_DIFF,
                "base_ref": "main",
                "head_ref": "feature/test",
                "github_token": "ghp_fake",
                "commit_sha": "abc1234",
                "create_pr": True,
            },
            headers={"X-API-Key": TEST_API_KEY},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_auto_review_unauthenticated(client):
    resp = await client.post(
        "/api/v1/auto-review",
        json={
            "repository": TEST_REPO,
            "pr_number": 1,
            "diff_raw": SAMPLE_DIFF,
            "base_ref": "main",
            "head_ref": "feature/test",
            "github_token": "ghp_fake",
            "commit_sha": "abc1234",
        },
    )
    assert resp.status_code == 401
