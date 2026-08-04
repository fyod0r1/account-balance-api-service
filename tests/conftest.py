from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_session
from app.main import app
from app.models import Account, Payment, User, UserRole
from app.security import hash_password


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

    try:
        async with Session() as session:
            yield session
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_settings() -> Settings:
        return Settings(
            database_url="sqlite+aiosqlite://",
            jwt_secret_key="test-secret-use-at-least-32-bytes",
            payment_webhook_secret="gfdmhghif38yrf9ew0jkf32",
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
