"""Layer 5 - HTTP routes: orders + wallet."""
from flask import Blueprint, jsonify, request

from ..errors import ServiceError
from ..security import api_login_required
from ..services import escrow_service

bp = Blueprint("orders", __name__, url_prefix="/api")


@bp.post("/orders/checkout")
@api_login_required
def checkout(user):
    item_id = (request.get_json(silent=True) or {}).get("item_id")
    if not item_id:
        raise ServiceError("item_id is required")
    return jsonify(escrow_service.start_checkout(user, item_id))


@bp.get("/orders")
@api_login_required
def list_orders(user):
    role = "selling" if request.args.get("role") == "selling" else "buying"
    return jsonify(escrow_service.my_orders(user["id"], role))


@bp.post("/orders/<order_id>/ship")
@api_login_required
def ship(user, order_id):
    return jsonify(escrow_service.mark_shipped(user["id"], order_id))


@bp.post("/orders/<order_id>/confirm-received")
@api_login_required
def received(user, order_id):
    return jsonify(escrow_service.confirm_received(user["id"], order_id))


@bp.post("/orders/<order_id>/refund")
@api_login_required
def refund(user, order_id):
    return jsonify(escrow_service.refund(user["id"], order_id))


@bp.post("/orders/<order_id>/cancel")
@api_login_required
def cancel(user, order_id):
    return jsonify(escrow_service.cancel_pending(user["id"], order_id))


@bp.post("/orders/<order_id>/dispute")
@api_login_required
def dispute(user, order_id):
    return jsonify(escrow_service.open_dispute(user["id"], order_id))


@bp.get("/wallet")
@api_login_required
def wallet(user):
    return jsonify(escrow_service.wallet(user["id"]))
