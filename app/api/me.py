from sanic import Blueprint, Request

from app.http import bearer_token, list_response, model_response, session_factory, settings
from app.schemas import AccountPublic, PaymentPublic, UserPublic
from app.services.auth import AuthService
from app.services.users import UserService

me_bp = Blueprint("me", url_prefix="/api/v1/me")


@me_bp.get("")
async def read_me(request: Request):
    async with session_factory(request)() as session:
        user = await AuthService(session, settings(request)).current_user(bearer_token(request))
        return model_response(UserPublic.model_validate(user))


@me_bp.get("/accounts")
async def read_my_accounts(request: Request):
    async with session_factory(request)() as session:
        user = await AuthService(session, settings(request)).current_user(bearer_token(request))
        accounts = await UserService(session).accounts_for_user(user.id)
        return list_response([AccountPublic.model_validate(account) for account in accounts])


@me_bp.get("/payments")
async def read_my_payments(request: Request):
    async with session_factory(request)() as session:
        user = await AuthService(session, settings(request)).current_user(bearer_token(request))
        payments = await UserService(session).payments_for_user(user.id)
        return list_response([PaymentPublic.model_validate(payment) for payment in payments])
