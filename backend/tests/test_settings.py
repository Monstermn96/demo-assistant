import pytest


@pytest.mark.asyncio
async def test_get_settings_unauthenticated(client):
    """Settings endpoint should reject unauthenticated requests."""
    resp = await client.get("/api/settings")
    assert resp.status_code in (401, 403)  # Rejected without credentials


@pytest.mark.asyncio
async def test_get_settings_default(auth_client):
    """GET /api/settings returns sensible defaults for a new user."""
    client, user_id = auth_client
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model"] is None
    assert data["temperature"] == 0.7
    assert data["max_tokens"] == -1
    assert data["top_p"] == 1.0
    assert data["context_length"] is None


@pytest.mark.asyncio
async def test_update_settings_temperature(auth_client):
    """PUT /api/settings can update temperature."""
    client, user_id = auth_client
    resp = await client.put("/api/settings", json={"temperature": 1.2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["temperature"] == 1.2
    # Other fields should keep their defaults
    assert data["top_p"] == 1.0
    assert data["max_tokens"] == -1


@pytest.mark.asyncio
async def test_update_default_model(auth_client):
    """PUT /api/settings can set a default model."""
    client, user_id = auth_client
    resp = await client.put("/api/settings", json={"default_model": "mistralai/magistral-small-2509"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model"] == "mistralai/magistral-small-2509"


@pytest.mark.asyncio
async def test_update_multiple_fields(auth_client):
    """PUT /api/settings can update multiple fields at once."""
    client, user_id = auth_client
    resp = await client.put("/api/settings", json={
        "temperature": 0.5,
        "top_p": 0.9,
        "max_tokens": 4096,
        "context_length": 8192,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["temperature"] == 0.5
    assert data["top_p"] == 0.9
    assert data["max_tokens"] == 4096
    assert data["context_length"] == 8192


@pytest.mark.asyncio
async def test_settings_persist(auth_client):
    """Settings should persist across multiple requests."""
    client, user_id = auth_client

    # Update temperature
    resp = await client.put("/api/settings", json={"temperature": 1.5})
    assert resp.status_code == 200

    # Read back — temperature should be 1.5
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["temperature"] == 1.5


@pytest.mark.asyncio
async def test_update_partial_preserves_other_fields(auth_client):
    """Updating one field should not affect others."""
    client, user_id = auth_client

    # Set temperature and model
    await client.put("/api/settings", json={
        "temperature": 0.3,
        "default_model": "some/model",
    })

    # Update only top_p
    resp = await client.put("/api/settings", json={"top_p": 0.5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["top_p"] == 0.5
    assert data["temperature"] == 0.3
    assert data["default_model"] == "some/model"


@pytest.mark.asyncio
async def test_clear_default_model(auth_client):
    """Setting default_model to null should clear it."""
    client, user_id = auth_client

    # Set a model
    await client.put("/api/settings", json={"default_model": "some/model"})

    # Clear it
    resp = await client.put("/api/settings", json={"default_model": None})
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model"] is None


@pytest.mark.asyncio
async def test_temperature_validation(auth_client):
    """Temperature must be between 0.0 and 2.0."""
    client, user_id = auth_client

    resp = await client.put("/api/settings", json={"temperature": 3.0})
    assert resp.status_code == 422  # Validation error

    resp = await client.put("/api/settings", json={"temperature": -0.5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_top_p_validation(auth_client):
    """Top P must be between 0.0 and 1.0."""
    client, user_id = auth_client

    resp = await client.put("/api/settings", json={"top_p": 1.5})
    assert resp.status_code == 422

    resp = await client.put("/api/settings", json={"top_p": -0.1})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_context_length_validation(auth_client):
    """Context length must be at least 256 when set."""
    client, user_id = auth_client

    resp = await client.put("/api/settings", json={"context_length": 100})
    assert resp.status_code == 422

    resp = await client.put("/api/settings", json={"context_length": 8192})
    assert resp.status_code == 200
