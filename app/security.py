import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt

from app.config import Settings


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = 210_000) -> str:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_raw)
        expected = base64.b64decode(digest_raw)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_raw))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: int, role: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, str]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def format_signature_amount(amount: Decimal) -> str:
    normalized = amount.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def build_payment_signature(
    *, account_id: int, amount: Decimal, transaction_id: str, user_id: int, secret_key: str
) -> str:
    raw = f"{account_id}{format_signature_amount(amount)}{transaction_id}{user_id}{secret_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_payment_signature(
    *,
    account_id: int,
    amount: Decimal,
    transaction_id: str,
    user_id: int,
    signature: str,
    secret_key: str,
) -> bool:
    expected = build_payment_signature(
        account_id=account_id,
        amount=amount,
        transaction_id=transaction_id,
        user_id=user_id,
        secret_key=secret_key,
    )
    return hmac.compare_digest(expected, signature)
