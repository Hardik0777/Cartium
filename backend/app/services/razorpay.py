"""Minimal Razorpay client: create an order, and verify the signature Checkout sends back.
Docs: https://razorpay.com/docs/payments/server-integration/python/"""
import hashlib
import hmac

import httpx

from app.core.config import settings

class PaymentsNotConfigured(Exception):
    pass


class RazorpayError(Exception):
    pass


def _require_keys():
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise PaymentsNotConfigured("Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to backend/.env")


def create_order(amount_paise: int, receipt: str) -> str:
    """Returns Razorpay's order id (order_XXXX)."""
    _require_keys()
    try:
        res = httpx.post(
            f"{settings.razorpay_api_url}/orders",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise RazorpayError("Couldn't reach Razorpay. Try again in a moment.") from exc
    if res.status_code != 200:
        # Razorpay explains the problem in error.description (e.g. wrong keys).
        detail = res.json().get("error", {}).get("description", res.text[:200]) if res.content else ""
        raise RazorpayError(f"Razorpay rejected the order: {detail}")
    return res.json()["id"]


def signature_is_valid(razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> bool:
    """Razorpay signs order_id|payment_id with our secret. Only Razorpay (and we) can produce it,
    so a valid signature proves the payment really happened for this order."""
    _require_keys()
    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)  # constant-time compare


def refund_payment(payment_id: str, amount_paise: int, note: str) -> str:
    """Refunds part or all of a captured payment. Returns Razorpay's refund id (rfnd_XXXX)."""
    _require_keys()
    try:
        res = httpx.post(
            f"{settings.razorpay_api_url}/payments/{payment_id}/refund",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json={"amount": amount_paise, "notes": {"reason": note[:200]}},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise RazorpayError("Couldn't reach Razorpay. Try again in a moment.") from exc
    if res.status_code != 200:
        detail = res.json().get("error", {}).get("description", res.text[:200]) if res.content else ""
        raise RazorpayError(f"Razorpay rejected the refund: {detail}")
    return res.json()["id"]
