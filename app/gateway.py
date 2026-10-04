"""Payment-gateway adapter.

This is a SANDBOX implementation so the project runs without a merchant
account. To go live, replace create_payment() with a call to the real
gateway SDK (e.g. Razorpay 'create order') and keep the same return type.
The webhook signature scheme (HMAC-SHA256) mirrors what real gateways use.
"""
import hashlib
import hmac
import uuid
from dataclasses import dataclass


@dataclass
class PaymentResult:
    ok: bool
    ref: str = ""
    url: str = ""


def create_payment(order_id, amount):
    ref = f"pay_{uuid.uuid4().hex[:16]}"
    return PaymentResult(ok=True, ref=ref, url=f"/payments/checkout/{ref}")


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign(body, secret), signature or "")
