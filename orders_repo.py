"""Layer 2 - Data access: orders, payments, ledger."""


def create(db, order):
    db.execute(
        """INSERT INTO orders (id, item_id, buyer_id, seller_id, amount_minor, fee_minor, status)
           VALUES (:id,:item_id,:buyer_id,:seller_id,:amount_minor,:fee_minor,'PENDING_PAYMENT')""",
        order,
    )


def create_payment(db, reference, order_id, provider):
    db.execute("INSERT INTO payments (reference, order_id, provider) VALUES (?,?,?)", (reference, order_id, provider))


def payment(db, reference):
    return db.execute("SELECT * FROM payments WHERE reference = ?", (reference,)).fetchone()


def payment_for_order(db, order_id):
    return db.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,)).fetchone()


def mark_payment_paid(db, reference):
    db.execute("UPDATE payments SET status = 'PAID' WHERE reference = ?", (reference,))


def get(db, order_id):
    return db.execute(
        """SELECT o.*, i.title AS item_title, i.image AS item_image,
                  b.name AS buyer_name, s.name AS seller_name
           FROM orders o
           JOIN items i ON i.id = o.item_id
           JOIN users b ON b.id = o.buyer_id
           JOIN users s ON s.id = o.seller_id
           WHERE o.id = ?""",
        (order_id,),
    ).fetchone()


def for_user(db, user_id, role):
    col = "buyer_id" if role == "buying" else "seller_id"
    return db.execute(
        f"""SELECT o.*, i.title AS item_title, i.image AS item_image,
                   b.name AS buyer_name, s.name AS seller_name
            FROM orders o
            JOIN items i ON i.id = o.item_id
            JOIN users b ON b.id = o.buyer_id
            JOIN users s ON s.id = o.seller_id
            WHERE o.{col} = ? ORDER BY o.created_at DESC""",
        (user_id,),
    ).fetchall()


def transition(db, order_id, allowed_from, new_status, stamp=None):
    """Atomic compare-and-set on status. Returns True only if this call made the change.
    This is what makes 'release funds' impossible to run twice."""
    marks = ",".join("?" * len(allowed_from))
    extra = f", {stamp} = datetime('now')" if stamp else ""
    cur = db.execute(
        f"UPDATE orders SET status = ?{extra} WHERE id = ? AND status IN ({marks})",
        [new_status, order_id, *allowed_from],
    )
    return cur.rowcount == 1


def add_ledger(db, order_id, user_id, entry_type, amount_minor):
    db.execute(
        "INSERT INTO ledger (order_id, user_id, entry_type, amount_minor) VALUES (?,?,?,?)",
        (order_id, user_id, entry_type, amount_minor),
    )


def ledger_for_user(db, user_id, limit=30):
    return db.execute(
        "SELECT * FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()


def stale_pending(db, minutes):
    return db.execute(
        "SELECT id, item_id FROM orders WHERE status = 'PENDING_PAYMENT' AND created_at < datetime('now', ?)",
        (f"-{int(minutes)} minutes",),
    ).fetchall()
