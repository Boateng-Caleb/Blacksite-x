"""Session auth + CSRF helpers used by the route layer."""
import hmac
import secrets
from functools import wraps

from flask import abort, jsonify, redirect, request, session, url_for

from .db import get_db
from .repositories import users_repo


def current_user():
    uid = session.get("user_id")
    return users_repo.by_id(get_db(), uid) if uid else None


def api_login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if not user:
            return jsonify(error="Please log in"), 401
        return fn(user, *a, **kw)
    return wrapper


def page_login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if not user:
            return redirect(url_for("pages.login", next=request.path))
        return fn(user, *a, **kw)
    return wrapper


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def init_app(app):
    @app.before_request
    def _csrf_check():
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.endpoint not in app.config["CSRF_EXEMPT"]:
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
            expected = session.get("csrf", "")
            if not expected or not hmac.compare_digest(sent, expected):
                abort(400, description="Bad CSRF token")

    @app.context_processor
    def _inject():
        return {"csrf_token": csrf_token(), "me": current_user(), "currency": app.config["CURRENCY"]}
