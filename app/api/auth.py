from sanic import Blueprint, Request

from app.http import model_response, parse_body, session_factory, settings
from app.schemas import LoginRequest, TokenResponse
from app.services.auth import AuthService

auth_bp = Blueprint("auth", url_prefix="/api/v1/auth")


@auth_bp.post("/login")
async def login(request: Request):
    payload = parse_body(request, LoginRequest)
    async with session_factory(request)() as session:
        token = await AuthService(session, settings(request)).login(payload.email, payload.password)
        return model_response(TokenResponse(access_token=token))
