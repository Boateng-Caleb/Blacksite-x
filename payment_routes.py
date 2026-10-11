"""Layer 5 - HTTP routes: payment callbacks, webhook, mock checkout."""
import json

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from ..db import get_db
from ..gateways.payment import valid_paystack_signature
from ..repositories import orders_repo
from ..security import page_login_required
from ..services import escrow_service

bp = Blueprint("payments", __name__, url_prefix="/payments")


@bp.get("/callback")
def callback():
    ref = request.args.get("reference") or request.args.get("trxref")
    if not ref:
        abort(400)
    escrow_service.confirm_payment(ref)
    return redirect(url_for("pages.orders"))


@bp.post("/webhook/paystack")
def paystack_webhook():
    if not valid_paystack_signature(request.get_data(), request.headers.get("X-Paystack-Signature")):
        abort(401)
    event = json.loads(request.get_data() or b"{}")
    if event.get("event") == "charge.success":
        escrow_service.confirm_payment(event["data"]["reference"])
    return "", 200


# ---- development-only simulated checkout --------------------------------
def _mock_only():
    if current_app.config["PAYMENT_PROVIDER"] != "mock":
        abort(404)


@bp.get("/mock/<reference>")
@page_login_required
def mock_checkout(user, reference):
    _mock_only()
    pay = orders_repo.payment(get_db(), reference)
    if not pay:
        abort(404)
    order = orders_repo.get(get_db(), pay["order_id"])
    if order["buyer_id"] != user["id"]:
        abort(404)
    return render_template("mock_checkout.html", order=escrow_service.serialize(order), reference=reference, page="mock")


@bp.post("/mock/<reference>/pay")
@page_login_required
def mock_pay(user, reference):
    _mock_only()
    pay = orders_repo.payment(get_db(), reference)
    if not pay:
        abort(404)
    order = orders_repo.get(get_db(), pay["order_id"])
    if order["buyer_id"] != user["id"]:
        abort(404)
    with get_db():
        orders_repo.mark_payment_paid(get_db(), reference)
    return redirect(url_for("payments.callback", reference=reference))
