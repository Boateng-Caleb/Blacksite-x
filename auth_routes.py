"""Layer 5 - HTTP routes: authentication (thin: parse -> service -> JSON)."""
from flask import Blueprint, jsonify, request, session

from ..security import api_login_required, current_user
from ..services import auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/signup")
def signup():
    d = request.get_json(silent=True) or {}
    user = auth_service.signup(d.get("name"), d.get("email"), d.get("phone"), d.get("password"))
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(auth_service.public_user(user)), 201


@bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    user = auth_service.login(d.get("email"), d.get("password"))
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(auth_service.public_user(user))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
def me():
    u = current_user()
    return jsonify(auth_service.public_user(u) if u else None)
