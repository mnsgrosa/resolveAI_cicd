from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_review_success(client):
    owner, repo = TEST_REPO.split("/")

    with (
        patch(
            "app.routers.review.plan_review",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.review.generate_fixes",
            new_callable=AsyncMock,
            return_value=MOCK_PLAN,
        ),
        patch(
            "app.routers.review.post_review",
            new_callable=AsyncMock,
            return_value="42",
        ),
    ):
        resp = await client.post(
            "/api/v1/review",
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
    assert data["comments_count"] == 1
    assert "hardcoded secret" in data["summary"].lower()


@pytest.mark.asyncio
async def test_review_anthropic_failure(client):
    with patch(
        "app.routers.review.plan_review",
        new_callable=AsyncMock,
        side_effect=Exception("API timeout"),
    ):
        resp = await client.post(
            "/api/v1/review",
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

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_review_unauthenticated(client):
    resp = await client.post(
        "/api/v1/review",
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
