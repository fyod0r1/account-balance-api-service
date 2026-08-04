import asyncio
import os
import random
import uuid
from decimal import Decimal

import pytest
from sanic_testing import TestManager
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.main import create_app
from app.models import Account, Payment, User, UserRole
from tests.conftest import SanicClientAdapter
from tests.helpers import webhook_payload

pytestmark = pytest.mark.integration


@pytest.fixture
async def postgres_session():
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://account_balance:account_balance@localhost:5432/account_balance",
    )
    engine = create_async_engine(database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with Session() as session:
            yield session
    finally:  # pragma: no branch
        await engine.dispose()


@pytest.fixture
async def postgres_sessionmaker():
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://account_balance:account_balance@localhost:5432/account_balance",
    )
    engine = create_async_engine(database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield Session
    finally:
        await engine.dispose()


async def test_postgres_models_persist_payment_and_balance(postgres_session) -> None:
    user = await postgres_session.get(User, 1)
    assert user is not None
    assert user.role == UserRole.USER

    account_id = random.randint(100_000, 999_999)
    transaction_id = f"integration-{uuid.uuid4()}"
    account = Account(id=account_id, user_id=user.id, balance=Decimal("1000.00"))
    postgres_session.add(account)
    await postgres_session.flush()

    account = await postgres_session.get(Account, account_id, with_for_update=True)
    assert account is not None
    payment = Payment(
        transaction_id=transaction_id,
        user_id=user.id,
        account_id=account_id,
        amount=Decimal("125.50"),
    )
    postgres_session.add(payment)
    account.balance += payment.amount
    await postgres_session.commit()

    result = await postgres_session.execute(
        select(Payment).where(Payment.transaction_id == transaction_id)
    )
    stored_payment = result.scalar_one()
    stored_account = await postgres_session.get(Account, account_id)

    assert stored_payment.amount == Decimal("125.50")
    assert stored_account is not None
    assert stored_account.balance == Decimal("1125.50")

    await postgres_session.execute(delete(Account).where(Account.id == account_id))
    await postgres_session.commit()


async def test_postgres_webhook_flow_creates_payment_and_updates_balance(
    postgres_sessionmaker,
) -> None:
    account_id = random.randint(100_000, 999_999)
    transaction_id = f"integration-webhook-{uuid.uuid4()}"

    test_app = create_app(
        app_settings=Settings(
            database_url="postgresql+asyncpg://unused:unused@localhost/unused",
            jwt_secret_key="test-secret-use-at-least-32-bytes",
            payment_webhook_secret="gfdmhghif38yrf9ew0jkf32",
        ),
        app_session_factory=postgres_sessionmaker,
        dispose=lambda: None,
    )
    TestManager(test_app)

    async with test_app.asgi_client as sanic_client:
        client = SanicClientAdapter(sanic_client)
        response = await client.post(
            "/api/v1/payments/webhook",
            json=webhook_payload(
                transaction_id=transaction_id,
                account_id=account_id,
                amount=Decimal("77.25"),
            ),
        )

    assert response.status_code == 200
    assert response.json()["balance"] == "77.25"

    async with postgres_sessionmaker() as session:
        payment_result = await session.execute(
            select(Payment).where(Payment.transaction_id == transaction_id)
        )
        stored_payment = payment_result.scalar_one()
        stored_account = await session.get(Account, account_id)

        assert stored_payment.amount == Decimal("77.25")
        assert stored_account is not None
        assert stored_account.balance == Decimal("77.25")

        await session.execute(delete(Account).where(Account.id == account_id))
        await session.commit()


async def test_concurrent_duplicate_webhooks_increment_balance_once(
    postgres_sessionmaker,
) -> None:
    account_id = random.randint(100_000, 999_999)
    transaction_id = f"integration-duplicate-{uuid.uuid4()}"

    async with postgres_sessionmaker() as session:
        session.add(Account(id=account_id, user_id=1, balance=Decimal("0.00")))
        await session.commit()

    test_app = create_app(
        app_settings=Settings(
            database_url="postgresql+asyncpg://unused:unused@localhost/unused",
            jwt_secret_key="test-secret-use-at-least-32-bytes",
            payment_webhook_secret="gfdmhghif38yrf9ew0jkf32",
        ),
        app_session_factory=postgres_sessionmaker,
        dispose=lambda: None,
    )
    TestManager(test_app)

    payload = webhook_payload(
        transaction_id=transaction_id,
        account_id=account_id,
        amount=Decimal("42.00"),
    )
    async with test_app.asgi_client as sanic_client:
        client = SanicClientAdapter(sanic_client)
        first, second = await asyncio.gather(
            client.post("/api/v1/payments/webhook", json=payload),
            client.post("/api/v1/payments/webhook", json=payload),
        )

    assert {first.status_code, second.status_code} == {200}
    assert sorted([first.json()["duplicate"], second.json()["duplicate"]]) == [False, True]

    async with postgres_sessionmaker() as session:
        account = await session.get(Account, account_id)
        payment_result = await session.execute(
            select(Payment).where(Payment.transaction_id == transaction_id)
        )
        payments = list(payment_result.scalars().all())

        assert account is not None
        assert account.balance == Decimal("42.00")
        assert len(payments) == 1

        await session.execute(delete(Account).where(Account.id == account_id))
        await session.commit()
