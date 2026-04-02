import pytest

from tests.conftest import TEST_API_KEY, TEST_REPO


@pytest.mark.asyncio
async def test_upsert_and_get_pattern(client):
    owner, repo = TEST_REPO.split("/")
    content = "# Patterns\n- Use snake_case for variables\n- Add type hints"

    # Create
    resp = await client.put(
        f"/api/v1/patterns/{owner}/{repo}",
        json={"content": content},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == content
    assert data["repository"] == TEST_REPO

    # Read
    resp = await client.get(
        f"/api/v1/patterns/{owner}/{repo}",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == content


@pytest.mark.asyncio
async def test_update_pattern(client):
    owner, repo = TEST_REPO.split("/")

    await client.put(
        f"/api/v1/patterns/{owner}/{repo}",
        json={"content": "v1"},
        headers={"X-API-Key": TEST_API_KEY},
    )

    resp = await client.put(
        f"/api/v1/patterns/{owner}/{repo}",
        json={"content": "v2"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "v2"


@pytest.mark.asyncio
async def test_delete_pattern(client):
    owner, repo = TEST_REPO.split("/")

    await client.put(
        f"/api/v1/patterns/{owner}/{repo}",
        json={"content": "some content"},
        headers={"X-API-Key": TEST_API_KEY},
    )

    resp = await client.delete(
        f"/api/v1/patterns/{owner}/{repo}",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v1/patterns/{owner}/{repo}",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_pattern_not_found(client):
    resp = await client.get(
        "/api/v1/patterns/owner/nonexistent",
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_api_key(client):
    resp = await client.get(
        "/api/v1/patterns/owner/repo",
        headers={"X-API-Key": "invalid-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
