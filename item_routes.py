"""Layer 5 - HTTP routes: items."""
from flask import Blueprint, jsonify, request

from ..security import api_login_required
from ..services import item_service

bp = Blueprint("items", __name__, url_prefix="/api/items")


def _float(name):
    try:
        return float(request.args.get(name))
    except (TypeError, ValueError):
        return None


@bp.get("")
def explore():
    items = item_service.explore(
        _float("lat"), _float("lng"), _float("radius"),
        (request.args.get("q") or "").strip() or None,
        request.args.get("category") or None,
    )
    return jsonify(items)


@bp.get("/mine")
@api_login_required
def mine(user):
    return jsonify(item_service.my_items(user["id"]))


@bp.get("/<item_id>")
def one(item_id):
    return jsonify(item_service.get_item(item_id, _float("lat"), _float("lng")))


@bp.post("")
@api_login_required
def create(user):
    return jsonify(item_service.create_item(user["id"], request.form, request.files.get("image"))), 201


@bp.delete("/<item_id>")
@api_login_required
def remove(user, item_id):
    item_service.remove_item(user["id"], item_id)
    return jsonify(ok=True)
