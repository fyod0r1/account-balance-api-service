from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Account
from app.schemas import PaymentWebhookRequest
from app.services.auth import AuthService
from app.services.payments import PaymentService
from tests.helpers import webhook_payload


def service_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",
        jwt_secret_key="test-secret-use-at-least-32-bytes",
        payment_webhook_secret="gfdmhghif38yrf9ew0jkf32",
    )


async def test_payment_service_duplicate_webhook_does_not_change_balance(
    db_session: AsyncSession,
) -> None:
    service = PaymentService(db_session, service_settings())
    payload = PaymentWebhookRequest.model_validate(
        webhook_payload(transaction_id="service-duplicate", amount=Decimal("100"))
    )

    first_result = await service.process_webhook(payload)
    second_result = await service.process_webhook(payload)

    account = await db_session.get(Account, 1)
    assert account is not None
    assert first_result.duplicate is False
    assert second_result.duplicate is True
    assert account.balance == Decimal("1100.00")


async def test_payment_service_rejects_account_owned_by_another_user(
    db_session: AsyncSession,
) -> None:
    service = PaymentService(db_session, service_settings())
    payload = PaymentWebhookRequest.model_validate(
        webhook_payload(
            transaction_id="service-wrong-owner",
            user_id=1,
            account_id=2,
            amount=Decimal("10"),
        )
    )

    with pytest.raises(ApiError) as exc_info:
        await service.process_webhook(payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Account does not belong to user"


async def test_auth_service_rejects_regular_user_for_admin_flow(
    db_session: AsyncSession,
) -> None:
    settings = service_settings()
    auth_service = AuthService(db_session, settings)
    token = await auth_service.login("user@example.com", "userpass123")

    with pytest.raises(ApiError) as exc_info:
        await auth_service.require_admin(token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin role required"


async def test_payment_service_creates_missing_account(db_session: AsyncSession) -> None:
    service = PaymentService(db_session, service_settings())
    payload = PaymentWebhookRequest.model_validate(
        webhook_payload(transaction_id="service-new-account", account_id=10, amount=Decimal("50"))
    )

    result = await service.process_webhook(payload)

    accounts = await db_session.execute(select(Account).where(Account.id == 10))
    account = accounts.scalar_one()
    assert result.balance == Decimal("50.00")
    assert account.user_id == 1
