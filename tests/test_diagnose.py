from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import TEST_API_KEY, TEST_REPO

SAMPLE_CODE = """\
def get_user(user_id):
    db = connect("postgres://admin:password123@localhost/mydb")
    return db.query(f"SELECT * FROM users WHERE id = {user_id}")
"""

MOCK_DIAGNOSE_DATA = {
    "original_code": SAMPLE_CODE,
    "fixed_code": "def get_user(user_id):\n    db = connect(os.environ['DATABASE_URL'])\n    return db.query('SELECT * FROM users WHERE id = %s', (user_id,))\n",
    "diagnosis": "The function is vulnerable to SQL injection because user_id is interpolated directly into the query string without sanitization.",
    "pattern_violations": [
        {
            "pattern_name": "No hardcoded credentials",
            "description": "Database connection string contains a hardcoded password.",
            "severity": "critical",
        }
    ],
    "suggestions": [
        "Use parameterized queries: db.query('SELECT * FROM users WHERE id = %s', (user_id,))",
        "Move credentials to environment variables: os.environ['DATABASE_URL']",
    ],
    "summary": "Critical SQL injection vulnerability and hardcoded credentials detected.",
}


@pytest.mark.asyncio
async def test_diagnose_success(client):
    with patch(
        "app.routers.diagnose.diagnose_code",
        new_callable=AsyncMock,
        return_value=MOCK_DIAGNOSE_DATA,
    ):
        resp = await client.post(
            "/api/v1/diagnose",
            json={
                "repository": TEST_REPO,
                "code": SAMPLE_CODE,
                "issue_description": "Users can log in as other users by manipulating the URL",
                "file_path": "app/users.py",
            },
            headers={"X-API-Key": TEST_API_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["original_code"] == SAMPLE_CODE
    assert data["fixed_code"] != SAMPLE_CODE
    assert "sql injection" in data["diagnosis"].lower()
    assert len(data["pattern_violations"]) == 1
    assert data["pattern_violations"][0]["severity"] == "critical"
    assert len(data["suggestions"]) == 2
    assert data["summary"]


@pytest.mark.asyncio
async def test_diagnose_anthropic_failure(client):
    with patch(
        "app.routers.diagnose.diagnose_code",
        new_callable=AsyncMock,
        side_effect=Exception("API timeout"),
    ):
        resp = await client.post(
            "/api/v1/diagnose",
            json={
                "repository": TEST_REPO,
                "code": SAMPLE_CODE,
                "issue_description": "Something is broken",
                "file_path": "app/users.py",
            },
            headers={"X-API-Key": TEST_API_KEY},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_diagnose_unauthenticated(client):
    resp = await client.post(
        "/api/v1/diagnose",
        json={
            "repository": TEST_REPO,
            "code": SAMPLE_CODE,
            "issue_description": "Something is broken",
            "file_path": "app/users.py",
        },
    )
    assert resp.status_code == 401
