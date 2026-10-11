import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .errors import ServiceError


def new_id(prefix):
    """Unique, readable id, e.g. ITM-3F9A1C0B7D (40 bits from a uuid4)."""
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def to_minor(amount):
    """'12.50' -> 1250 (pesewas). Money is always stored as integers."""
    try:
        d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ServiceError("Invalid price")
    if d <= 0 or d > Decimal("10000000"):
        raise ServiceError("Price must be greater than 0")
    return int(d * 100)


def from_minor(minor):
    return f"{minor / 100:.2f}"
