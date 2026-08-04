from dataclasses import asdict

from sanic import Blueprint, Request

from app.http import model_response, parse_body, session_factory, settings
from app.schemas import PaymentWebhookRequest, PaymentWebhookResponse
from app.services.payments import PaymentService

payments_bp = Blueprint("payments", url_prefix="/api/v1/payments")


@payments_bp.post("/webhook")
async def handle_payment_webhook(request: Request):
    payload = parse_body(request, PaymentWebhookRequest)
    async with session_factory(request)() as session:
        result = await PaymentService(session, settings(request)).process_webhook(payload)
        return model_response(PaymentWebhookResponse(**asdict(result)))
