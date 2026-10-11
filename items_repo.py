"""Layer 2 - Data access: items."""

_BASE = """
SELECT i.*, u.name AS seller_name {dist}
FROM items i JOIN users u ON u.id = i.seller_id
"""


def create(db, item):
    db.execute(
        """INSERT INTO items (id, seller_id, title, description, category, price_minor,
                              lat, lng, address_text, image)
           VALUES (:id,:seller_id,:title,:description,:category,:price_minor,
                   :lat,:lng,:address_text,:image)""",
        item,
    )


def get(db, item_id, lat=None, lng=None):
    dist = ", haversine_km(?,?,i.lat,i.lng) AS distance_km" if lat is not None else ""
    params = [lat, lng] if lat is not None else []
    return db.execute(_BASE.format(dist=dist) + " WHERE i.id = ?", params + [item_id]).fetchone()


def search(db, lat=None, lng=None, radius_km=None, q=None, category=None, limit=60):
    has_geo = lat is not None and lng is not None
    dist = ", haversine_km(?,?,i.lat,i.lng) AS distance_km" if has_geo else ""
    params = [lat, lng] if has_geo else []
    where, wparams = ["i.status = 'ACTIVE'"], []
    if q:
        where.append("(i.title LIKE ? OR i.description LIKE ?)")
        wparams += [f"%{q}%", f"%{q}%"]
    if category:
        where.append("i.category = ?")
        wparams.append(category)
    sql = f"SELECT * FROM ({_BASE.format(dist=dist)} WHERE {' AND '.join(where)})"
    params += wparams
    if has_geo and radius_km:
        sql += " WHERE distance_km <= ?"
        params.append(radius_km)
    sql += " ORDER BY distance_km ASC, created_at DESC" if has_geo else " ORDER BY created_at DESC"
    sql += " LIMIT ?"
    params.append(limit)
    return db.execute(sql, params).fetchall()


def by_seller(db, seller_id):
    return db.execute(
        _BASE.format(dist="") + " WHERE i.seller_id = ? AND i.status != 'REMOVED' ORDER BY i.created_at DESC",
        (seller_id,),
    ).fetchall()


def set_status_if(db, item_id, expected, new):
    """Compare-and-set. Returns True only if the row was in the expected state."""
    cur = db.execute("UPDATE items SET status = ? WHERE id = ? AND status = ?", (new, item_id, expected))
    return cur.rowcount == 1
