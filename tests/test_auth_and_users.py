from httpx import AsyncClient

from tests.helpers import login


async def test_user_can_login_and_read_profile(client: AsyncClient) -> None:
    token = await login(client, "user@example.com", "userpass123")

    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "email": "user@example.com",
        "full_name": "Test User",
    }


async def test_user_cannot_access_admin_endpoints(client: AsyncClient) -> None:
    token = await login(client, "user@example.com", "userpass123")

    response = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_user_cannot_see_other_users_accounts_or_payments(client: AsyncClient) -> None:
    token = await login(client, "user@example.com", "userpass123")
    headers = {"Authorization": f"Bearer {token}"}

    accounts_response = await client.get("/api/v1/me/accounts", headers=headers)
    payments_response = await client.get("/api/v1/me/payments", headers=headers)

    assert accounts_response.status_code == 200
    assert [account["id"] for account in accounts_response.json()] == [1]
    assert payments_response.status_code == 200
    assert all(payment["user_id"] == 1 for payment in payments_response.json())


async def test_admin_can_create_update_list_and_delete_user(client: AsyncClient) -> None:
    token = await login(client, "admin@example.com", "adminpass123")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "new-user@example.com",
            "password": "newpass123",
            "full_name": "New User",
            "role": "user",
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"full_name": "Updated User"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Updated User"

    list_response = await client.get("/api/v1/admin/users", headers=headers)
    assert list_response.status_code == 200
    assert any(user["email"] == "new-user@example.com" for user in list_response.json())

    delete_response = await client.delete(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert delete_response.status_code == 204
