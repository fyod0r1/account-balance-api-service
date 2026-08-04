from sanic import Blueprint, Request
from sanic.response import empty

from app.http import (
    bearer_token,
    list_response,
    model_response,
    parse_body,
    session_factory,
    settings,
)
from app.schemas import AdminUserCreate, AdminUserUpdate, AdminUserWithAccounts
from app.services.auth import AuthService
from app.services.users import UserService

admin_users_bp = Blueprint("admin_users", url_prefix="/api/v1/admin/users")


@admin_users_bp.post("")
async def create_user(request: Request):
    payload = parse_body(request, AdminUserCreate)
    async with session_factory(request)() as session:
        await AuthService(session, settings(request)).require_admin(bearer_token(request))
        user = await UserService(session).create_user(payload)
        return model_response(AdminUserWithAccounts.model_validate(user), 201)


@admin_users_bp.get("")
async def list_users(request: Request):
    async with session_factory(request)() as session:
        await AuthService(session, settings(request)).require_admin(bearer_token(request))
        users = await UserService(session).list_users()
        return list_response([AdminUserWithAccounts.model_validate(user) for user in users])


@admin_users_bp.patch("/<user_id:int>")
async def update_user(request: Request, user_id: int):
    payload = parse_body(request, AdminUserUpdate)
    async with session_factory(request)() as session:
        await AuthService(session, settings(request)).require_admin(bearer_token(request))
        user = await UserService(session).update_user(user_id, payload)
        return model_response(AdminUserWithAccounts.model_validate(user))


@admin_users_bp.delete("/<user_id:int>")
async def delete_user(request: Request, user_id: int):
    async with session_factory(request)() as session:
        await AuthService(session, settings(request)).require_admin(bearer_token(request))
        await UserService(session).delete_user(user_id)
        return empty(status=204)
