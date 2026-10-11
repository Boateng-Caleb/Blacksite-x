"""Layer 0 - Configuration. Everything environment-specific lives here."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _path(value, default):
    p = os.environ.get(value, default)
    return p if os.path.isabs(p) else os.path.join(BASE_DIR, p)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE = _path("DATABASE_PATH", "data/market.db")
    UPLOAD_FOLDER = _path("UPLOAD_FOLDER", "app/static/uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB uploads
    ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}

    CURRENCY = os.environ.get("CURRENCY", "GHS")
    PLATFORM_FEE_PERCENT = float(os.environ.get("PLATFORM_FEE_PERCENT", "5"))
    PENDING_ORDER_MINUTES = int(os.environ.get("PENDING_ORDER_MINUTES", "30"))

    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock")  # mock | paystack
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
    CSRF_EXEMPT = {"payments.paystack_webhook"}
