"""Layer 4 - Business logic: items."""
import os
import uuid

from flask import current_app

from ..db import get_db
from ..errors import ServiceError
from ..repositories import items_repo
from ..utils import from_minor, new_id, to_minor
from . import escrow_service

CATEGORIES = ["electronics", "fashion", "home", "vehicles", "books", "sports", "food", "other"]


def serialize(row):
    d = {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "category": row["category"], "price": from_minor(row["price_minor"]),
        "currency": current_app.config["CURRENCY"], "lat": row["lat"], "lng": row["lng"],
        "address": row["address_text"], "status": row["status"], "seller_id": row["seller_id"],
        "seller_name": row["seller_name"] if "seller_name" in row.keys() else None,
        "image": f"/static/uploads/{row['image']}" if row["image"] else None,
        "created_at": row["created_at"],
    }
    if "distance_km" in row.keys() and row["distance_km"] is not None:
        d["distance_km"] = round(row["distance_km"], 1)
    return d


def _save_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXT"]:
        raise ServiceError("Photo must be PNG, JPG or WEBP")
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    return name


def _coord(value, lo, hi, label):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ServiceError(f"{label} is required - tap 'Use my current location'")
    if not lo <= v <= hi:
        raise ServiceError(f"{label} is out of range")
    return v


def create_item(seller_id, form, file):
    title = (form.get("title") or "").strip()
    if len(title) < 3:
        raise ServiceError("Title must be at least 3 characters")
    category = form.get("category") or "other"
    if category not in CATEGORIES:
        raise ServiceError("Invalid category")
    item = {
        "id": new_id("ITM"),  # unique id for every uploaded item
        "seller_id": seller_id, "title": title[:120],
        "description": (form.get("description") or "").strip()[:2000],
        "category": category, "price_minor": to_minor(form.get("price")),
        "lat": _coord(form.get("lat"), -90, 90, "Latitude"),
        "lng": _coord(form.get("lng"), -180, 180, "Longitude"),
        "address_text": (form.get("address") or "").strip()[:200],
        "image": _save_image(file),
    }
    db = get_db()
    with db:
        items_repo.create(db, item)
    return serialize(items_repo.get(db, item["id"]))


def explore(lat, lng, radius_km, q, category):
    db = get_db()
    with db:
        escrow_service.expire_stale_orders(db)
    rows = items_repo.search(db, lat, lng, radius_km, q, category)
    return [serialize(r) for r in rows]


def get_item(item_id, lat=None, lng=None):
    row = items_repo.get(get_db(), item_id, lat, lng)
    if not row or row["status"] == "REMOVED":
        raise ServiceError("Item not found", 404)
    return serialize(row)


def my_items(seller_id):
    return [serialize(r) for r in items_repo.by_seller(get_db(), seller_id)]


def remove_item(seller_id, item_id):
    db = get_db()
    row = items_repo.get(db, item_id)
    if not row or row["seller_id"] != seller_id:
        raise ServiceError("Item not found", 404)
    with db:
        if not items_repo.set_status_if(db, item_id, "ACTIVE", "REMOVED"):
            raise ServiceError("Only active listings can be removed (this one is in an order)", 409)
