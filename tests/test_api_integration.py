import pytest


async def register_and_login(
    client,
    email: str = "alex@example.com",
    password: str = "password123",
):
    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Alex Operator",
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    return login_response.json()


@pytest.mark.asyncio
async def test_health_endpoint(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_me_returns_current_user(client) -> None:
    tokens = await register_and_login(client)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alex@example.com"


@pytest.mark.asyncio
async def test_refresh_rotates_tokens_and_allows_new_session(client) -> None:
    tokens = await register_and_login(client)

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"] != tokens["access_token"]
    assert refreshed["refresh_token"] != tokens["refresh_token"]

    me_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me_response.status_code == 200


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client) -> None:
    tokens = await register_and_login(client)

    logout_response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout_response.status_code == 204

    me_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 401
    assert me_response.json()["detail"] == "Token has been revoked."


@pytest.mark.asyncio
async def test_tasks_endpoints_create_list_update_and_cache(client, redis_client) -> None:
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_response = await client.post(
        "/tasks",
        headers=headers,
        json={
            "title": "Prepare customer rollout",
            "description": "Coordinate release windows",
            "status": "pending",
        },
    )
    assert create_response.status_code == 201
    created_task = create_response.json()
    assert created_task["title"] == "Prepare customer rollout"

    cache_key = "tasks:owner:1"
    assert await redis_client.get(cache_key) is None

    list_response = await client.get("/tasks", headers=headers)
    assert list_response.status_code == 200
    listed_tasks = list_response.json()
    assert len(listed_tasks) == 1
    assert listed_tasks[0]["id"] == created_task["id"]
    assert await redis_client.get(cache_key) is not None

    update_response = await client.patch(
        f"/tasks/{created_task['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "completed"
    assert await redis_client.get(cache_key) is None

    second_list_response = await client.get("/tasks", headers=headers)
    assert second_list_response.status_code == 200
    assert second_list_response.json()[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_tasks_endpoint_requires_authentication(client) -> None:
    response = await client.get("/tasks")

    assert response.status_code == 401
