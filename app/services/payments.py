from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Account, Payment, User, UserRole
from app.schemas import PaymentWebhookRequest
from app.security import verify_payment_signature


@dataclass(frozen=True)
class PaymentWebhookResult:
    transaction_id: str
    account_id: int
    user_id: int
    amount: Decimal
    balance: Decimal
    duplicate: bool = False


class PaymentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def process_webhook(self, payload: PaymentWebhookRequest) -> PaymentWebhookResult:
        self._verify_signature(payload)

        existing_payment = await self._payment_by_transaction_id(payload.transaction_id)
        if existing_payment is not None:
            return await self._duplicate_result(existing_payment)

        user = await self._session.get(User, payload.user_id)
        if user is None or user.role != UserRole.USER:
            raise ApiError(404, "User not found")

        try:
            async with self._session.begin_nested():
                account = await self._get_or_create_account(payload)
                payment = Payment(
                    transaction_id=payload.transaction_id,
                    user_id=payload.user_id,
                    account_id=payload.account_id,
                    amount=payload.amount,
                )
                self._session.add(payment)
                account.balance += payload.amount
                await self._session.flush()
                balance = account.balance
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            duplicate_payment = await self._payment_by_transaction_id(payload.transaction_id)
            if duplicate_payment is None:
                raise
            return await self._duplicate_result(duplicate_payment)

        return PaymentWebhookResult(
            transaction_id=payload.transaction_id,
            account_id=payload.account_id,
            user_id=payload.user_id,
            amount=payload.amount,
            balance=balance,
        )

    def _verify_signature(self, payload: PaymentWebhookRequest) -> None:
        if not verify_payment_signature(
            account_id=payload.account_id,
            amount=payload.amount,
            transaction_id=payload.transaction_id,
            user_id=payload.user_id,
            signature=payload.signature,
            secret_key=self._settings.payment_webhook_secret,
        ):
            raise ApiError(400, "Invalid signature")

    async def _payment_by_transaction_id(self, transaction_id: str) -> Payment | None:
        result = await self._session.execute(
            select(Payment).where(Payment.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def _get_or_create_account(self, payload: PaymentWebhookRequest) -> Account:
        account_result = await self._session.execute(
            select(Account).where(Account.id == payload.account_id).with_for_update()
        )
        account = account_result.scalar_one_or_none()
        if account is None:
            account = Account(
                id=payload.account_id,
                user_id=payload.user_id,
                balance=Decimal("0.00"),
            )
            self._session.add(account)
            await self._session.flush()
            return account

        if account.user_id != payload.user_id:
            raise ApiError(400, "Account does not belong to user")
        return account

    async def _duplicate_result(self, payment: Payment) -> PaymentWebhookResult:
        account = await self._session.get(Account, payment.account_id)
        if account is None:
            raise ApiError(409, "Stored payment account is missing")
        return PaymentWebhookResult(
            transaction_id=payment.transaction_id,
            account_id=payment.account_id,
            user_id=payment.user_id,
            amount=payment.amount,
            balance=account.balance,
            duplicate=True,
        )
