import uuid
from collections.abc import Callable
from typing import Any

from sanic import Request, Sanic
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.admin_users import admin_users_bp
from app.api.auth import auth_bp
from app.api.me import me_bp
from app.api.payments import payments_bp
from app.api.system import system_bp
from app.config import Settings, get_settings
from app.db import SessionLocal, engine
from app.errors import ApiError

SessionFactory = async_sessionmaker[AsyncSession]


def create_app(
    app_settings: Settings | None = None,
    app_session_factory: SessionFactory | None = None,
    dispose: Callable[[], Any] | None = None,
    name: str | None = None,
) -> Sanic:
    sanic_app = Sanic(name or f"account-balance-api-service-{uuid.uuid4().hex}")
    sanic_app.asgi = True
    sanic_app.ctx.settings = app_settings or get_settings()
    sanic_app.ctx.session_factory = app_session_factory or SessionLocal
    sanic_app.ctx.dispose = dispose or engine.dispose

    sanic_app.blueprint(system_bp)
    sanic_app.blueprint(auth_bp)
    sanic_app.blueprint(me_bp)
    sanic_app.blueprint(admin_users_bp)
    sanic_app.blueprint(payments_bp)

    @sanic_app.exception(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return json({"detail": exc.detail}, status=exc.status_code)

    @sanic_app.before_server_stop
    async def close_database(app_: Sanic) -> None:
        dispose_result = app_.ctx.dispose()
        if hasattr(dispose_result, "__await__"):
            await dispose_result

    return sanic_app


app = create_app(name="account_balance_api_service")
