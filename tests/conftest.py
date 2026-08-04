from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sanic_testing import TestManager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import Account, Payment, User, UserRole
from app.security import hash_password


class SanicClientAdapter:
    def __init__(self, client):
        self._client = client

    async def get(self, *args, **kwargs):
        _, response = await self._client.get(*args, **kwargs)
        return SanicResponseAdapter(response)

    async def post(self, *args, **kwargs):
        _, response = await self._client.post(*args, **kwargs)
        return SanicResponseAdapter(response)

    async def patch(self, *args, **kwargs):
        _, response = await self._client.patch(*args, **kwargs)
        return SanicResponseAdapter(response)

    async def delete(self, *args, **kwargs):
        _, response = await self._client.delete(*args, **kwargs)
        return SanicResponseAdapter(response)


class SanicResponseAdapter:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code

    def json(self):
        return self._response.json


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with Session() as session:
        session.add_all(
            [
                User(
                    id=1,
                    email="user@example.com",
                    full_name="Test User",
                    password_hash=hash_password("userpass123"),
                    role=UserRole.USER,
                ),
                User(
                    id=2,
                    email="admin@example.com",
                    full_name="Test Admin",
                    password_hash=hash_password("adminpass123"),
                    role=UserRole.ADMIN,
                ),
                User(
                    id=3,
                    email="other-user@example.com",
                    full_name="Other User",
                    password_hash=hash_password("otherpass123"),
                    role=UserRole.USER,
                ),
                Account(id=1, user_id=1, balance=1000),
                Account(id=2, user_id=3, balance=500),
                Payment(
                    transaction_id="other-user-payment",
                    user_id=3,
                    account_id=2,
                    amount=25,
                ),
            ]
        )
        await session.commit()

    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    class TestSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *_) -> None:
            return None

    test_app = create_app(
        app_settings=Settings(
            database_url="sqlite+aiosqlite://",
            jwt_secret_key="test-secret-use-at-least-32-bytes",
            payment_webhook_secret="gfdmhghif38yrf9ew0jkf32",
        ),
        app_session_factory=TestSessionFactory(),
        dispose=lambda: None,
    )
    TestManager(test_app)

    yield SanicClientAdapter(test_app.asgi_client)
    await test_app.asgi_client.aclose()
