"""Layer 3 - Payment gateway adapters.
The rest of the app only knows the 3 methods below, so providers can be swapped
without touching business logic."""
import hashlib
import hmac

import requests
from flask import current_app, url_for

from ..db import get_db
from ..repositories import orders_repo


class MockGateway:
    """Development gateway: a fake checkout page. NEVER use in production."""

    def initialize(self, reference, amount_minor, email, callback_url):
        return url_for("payments.mock_checkout", reference=reference, _external=True)

    def verify(self, reference):
        row = orders_repo.payment(get_db(), reference)
        order = orders_repo.get(get_db(), row["order_id"]) if row else None
        paid = bool(row and row["status"] == "PAID")
        return paid, (order["amount_minor"] if order else 0)

    def refund(self, reference, amount_minor):
        return True


class PaystackGateway:
    BASE = "https://api.paystack.co"

    def __init__(self, secret):
        self.h = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}

    def initialize(self, reference, amount_minor, email, callback_url):
        r = requests.post(
            f"{self.BASE}/transaction/initialize",
            headers=self.h,
            timeout=20,
            json={
                "email": email,
                "amount": amount_minor,
                "currency": current_app.config["CURRENCY"],
                "reference": reference,
                "callback_url": callback_url,
            },
        )
        r.raise_for_status()
        return r.json()["data"]["authorization_url"]

    def verify(self, reference):
        r = requests.get(f"{self.BASE}/transaction/verify/{reference}", headers=self.h, timeout=20)
        r.raise_for_status()
        d = r.json()["data"]
        return d["status"] == "success", int(d["amount"])

    def refund(self, reference, amount_minor):
        r = requests.post(
            f"{self.BASE}/refund", headers=self.h, timeout=20,
            json={"transaction": reference, "amount": amount_minor},
        )
        r.raise_for_status()
        return True


def get_gateway():
    if current_app.config["PAYMENT_PROVIDER"] == "paystack":
        return PaystackGateway(current_app.config["PAYSTACK_SECRET_KEY"])
    return MockGateway()


def valid_paystack_signature(raw_body: bytes, signature: str) -> bool:
    secret = current_app.config["PAYSTACK_SECRET_KEY"].encode()
    expected = hmac.new(secret, raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature or "")
