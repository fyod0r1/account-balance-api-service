from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.models import Account, Payment, User
from app.schemas import AdminUserCreate, AdminUserUpdate
from app.security import hash_password


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def accounts_for_user(self, user_id: int) -> list[Account]:
        result = await self._session.execute(select(Account).where(Account.user_id == user_id))
        return list(result.scalars().all())

    async def payments_for_user(self, user_id: int) -> list[Payment]:
        result = await self._session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_user(self, payload: AdminUserCreate) -> User:
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ApiError(409, "User email already exists") from exc
        return await self._user_with_accounts(user.id)

    async def list_users(self) -> list[User]:
        result = await self._session.execute(
            select(User).options(selectinload(User.accounts)).order_by(User.id)
        )
        return list(result.scalars().all())

    async def update_user(self, user_id: int, payload: AdminUserUpdate) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise ApiError(404, "User not found")

        if payload.email is not None:
            user.email = payload.email
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.password is not None:
            user.password_hash = hash_password(payload.password)
        if payload.role is not None:
            user.role = payload.role

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ApiError(409, "User email already exists") from exc
        return await self._user_with_accounts(user_id)

    async def delete_user(self, user_id: int) -> None:
        user = await self._session.get(User, user_id)
        if user is None:
            raise ApiError(404, "User not found")
        await self._session.delete(user)
        await self._session.commit()

    async def _user_with_accounts(self, user_id: int) -> User:
        result = await self._session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.accounts))
        )
        return result.scalar_one()
