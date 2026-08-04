from decimal import Decimal

from app.security import build_payment_signature


def webhook_payload(
    *,
    transaction_id: str = "5eae174f-7cd0-472c-bd36-35660f00132b",
    user_id: int = 1,
    account_id: int = 1,
    amount: Decimal = Decimal("100"),
    secret_key: str = "gfdmhghif38yrf9ew0jkf32",
) -> dict[str, object]:
    signature = build_payment_signature(
        account_id=account_id,
        amount=amount,
        transaction_id=transaction_id,
        user_id=user_id,
        secret_key=secret_key,
    )
    return {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "account_id": account_id,
        "amount": str(amount),
        "signature": signature,
    }


async def login(client, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]
