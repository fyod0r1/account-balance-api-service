from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.db import engine, get_session
from app.dependencies import authenticate_user, get_current_admin, get_current_user
from app.models import Account, Payment, User, UserRole
from app.schemas import (
    AccountPublic,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserWithAccounts,
    LoginRequest,
    PaymentPublic,
    PaymentWebhookRequest,
    PaymentWebhookResponse,
    TokenResponse,
    UserPublic,
)
from app.security import create_access_token, hash_password, verify_payment_signature


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Account Balance API Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value, settings),
    )


@app.get("/api/v1/me", response_model=UserPublic)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@app.get("/api/v1/me/accounts", response_model=list[AccountPublic])
async def read_my_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Account]:
    result = await session.execute(select(Account).where(Account.user_id == current_user.id))
    return list(result.scalars().all())


@app.get("/api/v1/me/payments", response_model=list[PaymentPublic])
async def read_my_payments(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Payment]:
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())


@app.post("/api/v1/admin/users", response_model=AdminUserWithAccounts, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    _: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="User email already exists") from exc
    result = await session.execute(
        select(User).where(User.id == user.id).options(selectinload(User.accounts))
    )
    return result.scalar_one()


@app.get("/api/v1/admin/users", response_model=list[AdminUserWithAccounts])
async def list_users(
    _: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[User]:
    result = await session.execute(
        select(User).options(selectinload(User.accounts)).order_by(User.id)
    )
    return list(result.scalars().all())


@app.patch("/api/v1/admin/users/{user_id}", response_model=AdminUserWithAccounts)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    _: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email is not None:
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="User email already exists") from exc

    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.accounts))
    )
    return result.scalar_one()


@app.delete("/api/v1/admin/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()


@app.post("/api/v1/payments/webhook", response_model=PaymentWebhookResponse)
async def handle_payment_webhook(
    payload: PaymentWebhookRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PaymentWebhookResponse:
    if not verify_payment_signature(
        account_id=payload.account_id,
        amount=payload.amount,
        transaction_id=payload.transaction_id,
        user_id=payload.user_id,
        signature=payload.signature,
        secret_key=settings.payment_webhook_secret,
    ):
        raise HTTPException(status_code=400, detail="Invalid signature")

    result = await session.execute(
        select(Payment).where(Payment.transaction_id == payload.transaction_id)
    )
    existing_payment = result.scalar_one_or_none()
    if existing_payment is not None:
        account = await session.get(Account, existing_payment.account_id)
        if account is None:
            raise HTTPException(status_code=409, detail="Stored payment account is missing")
        return PaymentWebhookResponse(
            transaction_id=existing_payment.transaction_id,
            account_id=existing_payment.account_id,
            user_id=existing_payment.user_id,
            amount=existing_payment.amount,
            balance=account.balance,
            duplicate=True,
        )

    user = await session.get(User, payload.user_id)
    if user is None or user.role != UserRole.USER:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        async with session.begin_nested():
            account_result = await session.execute(
                select(Account).where(Account.id == payload.account_id).with_for_update()
            )
            account = account_result.scalar_one_or_none()
            if account is None:
                account = Account(
                    id=payload.account_id,
                    user_id=payload.user_id,
                    balance=Decimal("0.00"),
                )
                session.add(account)
                await session.flush()
            elif account.user_id != payload.user_id:
                raise HTTPException(status_code=400, detail="Account does not belong to user")

            payment = Payment(
                transaction_id=payload.transaction_id,
                user_id=payload.user_id,
                account_id=payload.account_id,
                amount=payload.amount,
            )
            session.add(payment)
            account.balance += payload.amount
            await session.flush()
            balance = account.balance
        await session.commit()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(Payment).where(Payment.transaction_id == payload.transaction_id)
        )
        duplicate_payment = result.scalar_one()
        account = await session.get(Account, duplicate_payment.account_id)
        if account is None:
            raise HTTPException(
                status_code=409, detail="Stored payment account is missing"
            ) from None
        return PaymentWebhookResponse(
            transaction_id=duplicate_payment.transaction_id,
            account_id=duplicate_payment.account_id,
            user_id=duplicate_payment.user_id,
            amount=duplicate_payment.amount,
            balance=account.balance,
            duplicate=True,
        )

    return PaymentWebhookResponse(
        transaction_id=payload.transaction_id,
        account_id=payload.account_id,
        user_id=payload.user_id,
        amount=payload.amount,
        balance=balance,
    )
