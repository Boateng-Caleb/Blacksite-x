"""Layer 4 - Business logic: escrow payments.

Money flow
  buyer pays  -> platform holds funds            (order ESCROW_HELD, ledger ESCROW_HOLD)
  buyer taps 'I received it' -> seller wallet credited minus fee   (COMPLETED)
  cancel before completion   -> gateway refund to buyer             (REFUNDED)
Funds are NEVER released by the seller, by a timer, or by the gateway callback -
only by the buyer's confirmation.  Every state change is an atomic compare-and-set,
so a double click or a replayed request cannot release funds twice.
"""
from flask import current_app, url_for

from ..db import get_db
from ..errors import ServiceError
from ..gateways.payment import get_gateway
from ..repositories import items_repo, orders_repo, users_repo
from ..utils import from_minor, new_id


def serialize(o):
    return {
        "id": o["id"], "item_id": o["item_id"], "item_title": o["item_title"],
        "item_image": f"/static/uploads/{o['item_image']}" if o["item_image"] else None,
        "buyer_id": o["buyer_id"], "buyer_name": o["buyer_name"],
        "seller_id": o["seller_id"], "seller_name": o["seller_name"],
        "amount": from_minor(o["amount_minor"]), "fee": from_minor(o["fee_minor"]),
        "seller_receives": from_minor(o["amount_minor"] - o["fee_minor"]),
        "currency": current_app.config["CURRENCY"], "status": o["status"],
        "created_at": o["created_at"],
    }


def expire_stale_orders(db):
    """Release items whose buyer never finished paying."""
    for row in orders_repo.stale_pending(db, current_app.config["PENDING_ORDER_MINUTES"]):
        if orders_repo.transition(db, row["id"], ["PENDING_PAYMENT"], "CANCELLED"):
            items_repo.set_status_if(db, row["item_id"], "RESERVED", "ACTIVE")


def start_checkout(buyer, item_id):
    db = get_db()
    with db:
        expire_stale_orders(db)
    item = items_repo.get(db, item_id)
    if not item or item["status"] != "ACTIVE":
        raise ServiceError("This item is no longer available", 409)
    if item["seller_id"] == buyer["id"]:
        raise ServiceError("You cannot buy your own item")

    amount = item["price_minor"]
    fee = round(amount * current_app.config["PLATFORM_FEE_PERCENT"] / 100)
    order_id, reference = new_id("ORD"), new_id("PAY")
    provider = current_app.config["PAYMENT_PROVIDER"]

    with db:  # reserve the item so two buyers can't pay for it at once
        if not items_repo.set_status_if(db, item_id, "ACTIVE", "RESERVED"):
            raise ServiceError("This item was just taken by another buyer", 409)
        orders_repo.create(db, {"id": order_id, "item_id": item_id, "buyer_id": buyer["id"],
                                "seller_id": item["seller_id"], "amount_minor": amount, "fee_minor": fee})
        orders_repo.create_payment(db, reference, order_id, provider)

    try:
        checkout_url = get_gateway().initialize(
            reference, amount, buyer["email"], url_for("payments.callback", _external=True))
    except Exception:
        current_app.logger.exception("gateway initialize failed")
        with db:
            orders_repo.transition(db, order_id, ["PENDING_PAYMENT"], "CANCELLED")
            items_repo.set_status_if(db, item_id, "RESERVED", "ACTIVE")
        raise ServiceError("Payment provider unavailable, try again", 502)
    return {"order_id": order_id, "checkout_url": checkout_url}


def confirm_payment(reference):
    """Called from the browser callback AND the webhook. Idempotent.
    Funds are only trusted after we verify them with the gateway ourselves."""
    db = get_db()
    pay = orders_repo.payment(db, reference)
    if not pay:
        raise ServiceError("Unknown payment reference", 404)
    order = orders_repo.get(db, pay["order_id"])
    if order["status"] != "PENDING_PAYMENT":
        return order  # already processed
    paid, amount = get_gateway().verify(reference)
    if not paid:
        return order
    if amount != order["amount_minor"]:
        current_app.logger.error("amount mismatch on %s", reference)
        raise ServiceError("Payment amount mismatch", 400)
    with db:
        if orders_repo.transition(db, order["id"], ["PENDING_PAYMENT"], "ESCROW_HELD", "paid_at"):
            orders_repo.mark_payment_paid(db, reference)
            orders_repo.add_ledger(db, order["id"], order["buyer_id"], "ESCROW_HOLD", order["amount_minor"])
    return orders_repo.get(db, order["id"])


def _order_for(order_id, user_id, role):
    db = get_db()
    o = orders_repo.get(db, order_id)
    key = "buyer_id" if role == "buyer" else "seller_id"
    if not o or o[key] != user_id:
        raise ServiceError("Order not found", 404)
    return o


def mark_shipped(seller_id, order_id):
    o = _order_for(order_id, seller_id, "seller")
    db = get_db()
    with db:
        if not orders_repo.transition(db, o["id"], ["ESCROW_HELD"], "SHIPPED", "shipped_at"):
            raise ServiceError("Order must be paid and not yet shipped", 409)
    return serialize(orders_repo.get(db, o["id"]))


def confirm_received(buyer_id, order_id):
    """THE release step - only the buyer can trigger it."""
    o = _order_for(order_id, buyer_id, "buyer")
    db = get_db()
    with db:
        if not orders_repo.transition(db, o["id"], ["ESCROW_HELD", "SHIPPED"], "COMPLETED", "completed_at"):
            raise ServiceError("Funds are not in escrow for this order", 409)
        payout = o["amount_minor"] - o["fee_minor"]
        users_repo.credit_wallet(db, o["seller_id"], payout)
        orders_repo.add_ledger(db, o["id"], o["seller_id"], "ESCROW_RELEASE", payout)
        orders_repo.add_ledger(db, o["id"], None, "PLATFORM_FEE", o["fee_minor"])
        items_repo.set_status_if(db, o["item_id"], "RESERVED", "SOLD")
    return serialize(orders_repo.get(db, o["id"]))


def refund(user_id, order_id):
    """Buyer may refund before shipping; seller may refund any time before completion."""
    db = get_db()
    o = orders_repo.get(db, order_id)
    if not o or user_id not in (o["buyer_id"], o["seller_id"]):
        raise ServiceError("Order not found", 404)
    allowed = ["ESCROW_HELD"] if user_id == o["buyer_id"] else ["ESCROW_HELD", "SHIPPED"]
    with db:
        if not orders_repo.transition(db, o["id"], allowed, "REFUNDED"):
            raise ServiceError("This order can no longer be refunded by you", 409)
        orders_repo.add_ledger(db, o["id"], o["buyer_id"], "REFUND", o["amount_minor"])
        items_repo.set_status_if(db, o["item_id"], "RESERVED", "ACTIVE")
    pay = orders_repo.payment_for_order(db, o["id"])
    try:
        get_gateway().refund(pay["reference"], o["amount_minor"])
    except Exception:
        current_app.logger.exception("gateway refund failed for %s - needs manual refund", o["id"])
    return serialize(orders_repo.get(db, o["id"]))


def cancel_pending(buyer_id, order_id):
    o = _order_for(order_id, buyer_id, "buyer")
    db = get_db()
    with db:
        if not orders_repo.transition(db, o["id"], ["PENDING_PAYMENT"], "CANCELLED"):
            raise ServiceError("Only unpaid orders can be cancelled", 409)
        items_repo.set_status_if(db, o["item_id"], "RESERVED", "ACTIVE")
    return serialize(orders_repo.get(db, o["id"]))


def open_dispute(buyer_id, order_id):
    """Freezes the funds (neither released nor refunded) until an admin resolves it."""
    o = _order_for(order_id, buyer_id, "buyer")
    db = get_db()
    with db:
        if not orders_repo.transition(db, o["id"], ["SHIPPED"], "DISPUTED"):
            raise ServiceError("You can only dispute an order that was marked shipped", 409)
    return serialize(orders_repo.get(db, o["id"]))


def my_orders(user_id, role):
    return [serialize(o) for o in orders_repo.for_user(get_db(), user_id, role)]


def wallet(user_id):
    db = get_db()
    u = users_repo.by_id(db, user_id)
    entries = [{"type": e["entry_type"], "order_id": e["order_id"], "amount": from_minor(e["amount_minor"]),
                "created_at": e["created_at"]} for e in orders_repo.ledger_for_user(db, user_id)]
    return {"balance": from_minor(u["wallet_minor"]), "currency": current_app.config["CURRENCY"], "entries": entries}
