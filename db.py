"""Layer 1 - Database connection + schema."""
import math
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    wallet_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,                -- unique id, e.g. ITM-3F9A1C0B7D
    seller_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'other',
    price_minor INTEGER NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    address_text TEXT NOT NULL DEFAULT '',
    image TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | RESERVED | SOLD | REMOVED
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    buyer_id TEXT NOT NULL REFERENCES users(id),
    seller_id TEXT NOT NULL REFERENCES users(id),
    amount_minor INTEGER NOT NULL,
    fee_minor INTEGER NOT NULL,
    -- PENDING_PAYMENT | ESCROW_HELD | SHIPPED | DISPUTED | COMPLETED | REFUNDED | CANCELLED
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at TEXT, shipped_at TEXT, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    reference TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'INITIATED',  -- INITIATED | PAID
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    user_id TEXT,                        -- NULL = platform
    entry_type TEXT NOT NULL,            -- ESCROW_HOLD | ESCROW_RELEASE | PLATFORM_FEE | REFUND
    amount_minor INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"], timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.create_function("haversine_km", 4, _haversine_km, deterministic=True)
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        get_db().executescript(SCHEMA)
