from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class AccountPublic(BaseModel):
    id: int
    user_id: int
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class PaymentPublic(BaseModel):
    id: int
    transaction_id: str
    user_id: int
    account_id: int
    amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.USER


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None


class AdminUserWithAccounts(UserPublic):
    role: UserRole
    accounts: list[AccountPublic]


class PaymentWebhookRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=64)
    user_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    amount: Decimal = Field(gt=Decimal("0"))
    signature: str = Field(min_length=64, max_length=64)


class PaymentWebhookResponse(BaseModel):
    transaction_id: str
    account_id: int
    user_id: int
    amount: Decimal
    balance: Decimal
    duplicate: bool = False
