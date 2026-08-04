from typing import Any

from pydantic import BaseModel, ValidationError
from sanic import Request
from sanic.response import json

from app.config import Settings
from app.errors import ApiError


def model_response(model: BaseModel, status: int = 200):
    return json(model.model_dump(mode="json"), status=status)


def list_response(items: list[BaseModel], status: int = 200):
    return json([item.model_dump(mode="json") for item in items], status=status)


def parse_body[T: BaseModel](request: Request, schema: type[T]) -> T:
    try:
        return schema.model_validate(request.json or {})
    except ValidationError as exc:
        raise ApiError(422, exc.errors()) from exc


def bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "Invalid authentication token")
    return token


def session_factory(request: Request) -> Any:
    return request.app.ctx.session_factory


def settings(request: Request) -> Settings:
    return request.app.ctx.settings
