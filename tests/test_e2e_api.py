import os
import uuid
from decimal import Decimal

import httpx
import pytest

from tests.helpers import webhook_payload

pytestmark = pytest.mark.e2e


def require_e2e() -> str:
    if os.getenv("RUN_E2E_TESTS") != "1":
        pytest.skip("set RUN_E2E_TESTS=1 to run e2e tests")
    return os.getenv("E2E_API_URL", "http://localhost:8000")


async def test_running_app_full_user_admin_webhook_flow() -> None:
    api_url = require_e2e()
    async with httpx.AsyncClient(base_url=api_url, timeout=10) as client:
        health_response = await client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}

        user_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "userpass123"},
        )
        assert user_login.status_code == 200
        user_token = user_login.json()["access_token"]

        me_response = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "user@example.com"

        transaction_id = os.getenv("E2E_TRANSACTION_ID", "e2e-tx-1")
        webhook_response = await client.post(
            "/api/v1/payments/webhook",
            json=webhook_payload(transaction_id=transaction_id, amount=Decimal("10")),
        )
        assert webhook_response.status_code == 200
        assert webhook_response.json()["duplicate"] in {False, True}

        duplicate_response = await client.post(
            "/api/v1/payments/webhook",
            json=webhook_payload(transaction_id=transaction_id, amount=Decimal("10")),
        )
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["duplicate"] is True

        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "adminpass123"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        users_response = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert users_response.status_code == 200
        assert any(user["email"] == "user@example.com" for user in users_response.json())

        new_user_email = f"e2e-{uuid.uuid4()}@example.com"
        create_response = await client.post(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": new_user_email,
                "password": "newpass123",
                "full_name": "E2E User",
                "role": "user",
            },
        )
        assert create_response.status_code == 201
        new_user_id = create_response.json()["id"]

        update_response = await client.patch(
            f"/api/v1/admin/users/{new_user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"full_name": "Updated E2E User"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["full_name"] == "Updated E2E User"

        delete_response = await client.delete(
            f"/api/v1/admin/users/{new_user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert delete_response.status_code == 204
