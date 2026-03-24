import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "name" in data


@pytest.mark.asyncio
async def test_models_endpoint_returns_list(client):
    """Models endpoint should return a list (may be empty without LM Studio)."""
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert isinstance(data["models"], list)
