"""Layer 4 - Business logic: accounts."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from ..errors import ServiceError
from ..repositories import users_repo
from ..utils import new_id

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def signup(name, email, phone, password):
    name, email, phone = (name or "").strip(), (email or "").strip().lower(), (phone or "").strip()
    if len(name) < 2:
        raise ServiceError("Enter your full name")
    if not EMAIL_RE.match(email):
        raise ServiceError("Enter a valid email address")
    if len(password or "") < 8:
        raise ServiceError("Password must be at least 8 characters")
    db = get_db()
    if users_repo.by_email(db, email):
        raise ServiceError("An account with this email already exists", 409)
    user_id = new_id("USR")
    with db:
        users_repo.create(db, user_id, name, email, phone, generate_password_hash(password))
    return users_repo.by_id(db, user_id)


def login(email, password):
    user = users_repo.by_email(get_db(), (email or "").strip().lower())
    if not user or not check_password_hash(user["password_hash"], password or ""):
        raise ServiceError("Incorrect email or password", 401)
    return user


def public_user(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "wallet": f"{u['wallet_minor'] / 100:.2f}"}
