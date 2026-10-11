"""Layer 2 - Data access: users. Only SQL lives here."""


def create(db, user_id, name, email, phone, password_hash):
    db.execute(
        "INSERT INTO users (id, name, email, phone, password_hash) VALUES (?,?,?,?,?)",
        (user_id, name, email, phone, password_hash),
    )


def by_email(db, email):
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def by_id(db, user_id):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def credit_wallet(db, user_id, amount_minor):
    db.execute("UPDATE users SET wallet_minor = wallet_minor + ? WHERE id = ?", (amount_minor, user_id))
