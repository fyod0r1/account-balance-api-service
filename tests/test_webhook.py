from decimal import Decimal

from httpx import AsyncClient

from app.security import build_payment_signature
from tests.helpers import login, webhook_payload


async def test_signature_matches_assignment_example() -> None:
    assert (
        build_payment_signature(
            account_id=1,
            amount=Decimal("100"),
            transaction_id="5eae174f-7cd0-472c-bd36-35660f00132b",
            user_id=1,
            secret_key="gfdmhghif38yrf9ew0jkf32",
        )
        == "7b47e41efe564a062029da3367bde8844bea0fb049f894687cee5d57f2858bc8"
    )


async def test_webhook_replenishes_existing_account_once(client: AsyncClient) -> None:
    payload = webhook_payload(transaction_id="tx-1", amount=Decimal("100"))

    first_response = await client.post("/api/v1/payments/webhook", json=payload)
    second_response = await client.post("/api/v1/payments/webhook", json=payload)

    assert first_response.status_code == 200
    assert first_response.json()["duplicate"] is False
    assert first_response.json()["balance"] == "1100.00"
    assert second_response.status_code == 200
    assert second_response.json()["duplicate"] is True
    assert second_response.json()["balance"] == "1100.00"

    token = await login(client, "user@example.com", "userpass123")
    payments_response = await client.get(
        "/api/v1/me/payments", headers={"Authorization": f"Bearer {token}"}
    )
    assert payments_response.status_code == 200
    assert len(payments_response.json()) == 1


async def test_webhook_creates_missing_account(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments/webhook",
        json=webhook_payload(transaction_id="tx-new-account", account_id=10, amount=Decimal("50")),
    )

    assert response.status_code == 200
    assert response.json()["account_id"] == 10
    assert response.json()["balance"] == "50.00"


async def test_webhook_rejects_invalid_signature(client: AsyncClient) -> None:
    payload = webhook_payload(transaction_id="tx-invalid")
    payload["signature"] = "0" * 64

    response = await client.post("/api/v1/payments/webhook", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"


async def test_webhook_rejects_account_that_belongs_to_another_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments/webhook",
        json=webhook_payload(
            transaction_id="tx-wrong-owner",
            user_id=1,
            account_id=2,
            amount=Decimal("10"),
        ),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Account does not belong to user"
