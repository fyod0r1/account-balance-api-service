import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import User, UserRole
from app.security import create_access_token, decode_access_token, verify_password


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def login(self, email: str, password: str) -> str:
        user = await self._authenticate_user(email, password)
        if user is None:
            raise ApiError(401, "Invalid credentials")
        return create_access_token(user.id, user.role.value, self._settings)

    async def current_user(self, token: str) -> User:
        try:
            payload = decode_access_token(token, self._settings)
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise ApiError(401, "Invalid authentication token") from exc

        user = await self._session.get(User, user_id)
        if user is None:
            raise ApiError(401, "User not found")
        return user

    async def require_admin(self, token: str) -> User:
        user = await self.current_user(token)
        if user.role != UserRole.ADMIN:
            raise ApiError(403, "Admin role required")
        return user

    async def _authenticate_user(self, email: str, password: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user
