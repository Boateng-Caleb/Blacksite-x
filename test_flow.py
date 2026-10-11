"""End-to-end test of the escrow flow. Run: python -m unittest -v"""
import io
import os
import tempfile
import unittest

from app import create_app


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"DATABASE": os.path.join(self.tmp, "t.db"), "UPLOAD_FOLDER": self.tmp,
                               "TESTING": True, "PAYMENT_PROVIDER": "mock", "PLATFORM_FEE_PERCENT": 5})

    def client(self):
        return self.app.test_client()

    def post(self, c, url, **kw):
        return c.post(url, headers={"X-CSRF-Token": self._tok(c)}, **kw)

    def _tok(self, c):
        c.get("/")  # a page render issues the CSRF token (login/signup rotate the session)
        with c.session_transaction() as s:
            return s["csrf"]

    def signup(self, name, email):
        c = self.client()
        r = self.post(c, "/api/auth/signup", json={"name": name, "email": email, "password": "password123"})
        self.assertEqual(r.status_code, 201, r.json)
        return c

    def test_full_escrow_flow(self):
        seller, buyer = self.signup("Ama Seller", "a@x.com"), self.signup("Kofi Buyer", "k@x.com")
        r = self.post(seller, "/api/items", data={"title": "Laptop", "price": "100", "lat": "5.1053", "lng": "-1.2466",
                                                   "category": "electronics", "image": (io.BytesIO(b"x"), "a.png")},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201, r.json)
        item = r.json
        self.assertTrue(item["id"].startswith("ITM-"))

        near = buyer.get("/api/items?lat=5.11&lng=-1.25&radius=10").json
        far = buyer.get("/api/items?lat=6.69&lng=-1.62&radius=10").json  # Kumasi
        self.assertEqual(len(near), 1)
        self.assertEqual(len(far), 0)

        self.assertEqual(self.post(seller, "/api/orders/checkout", json={"item_id": item["id"]}).status_code, 400)  # own item
        r = self.post(buyer, "/api/orders/checkout", json={"item_id": item["id"]})
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(self.post(buyer, "/api/orders/checkout", json={"item_id": item["id"]}).status_code, 409)

        # callback before paying must NOT hold funds
        ref_url = r.json["checkout_url"].split("localhost")[-1]
        ref = ref_url.rsplit("/", 1)[-1]
        buyer.get(f"/payments/callback?reference={ref}")
        self.assertEqual(buyer.get("/api/orders?role=buying").json[0]["status"], "PENDING_PAYMENT")

        # pay on mock checkout
        buyer.post(f"/payments/mock/{ref}/pay", data={"csrf_token": self._tok(buyer)}, follow_redirects=True)
        order = buyer.get("/api/orders?role=buying").json[0]
        self.assertEqual(order["status"], "ESCROW_HELD")
        self.assertEqual(seller.get("/api/wallet").json["balance"], "0.00")

        # seller cannot release; buyer can, once
        self.assertEqual(self.post(seller, f"/api/orders/{order['id']}/confirm-received").status_code, 404)
        self.assertEqual(self.post(seller, f"/api/orders/{order['id']}/ship").status_code, 200)
        self.assertEqual(self.post(buyer, f"/api/orders/{order['id']}/confirm-received").status_code, 200)
        self.assertEqual(self.post(buyer, f"/api/orders/{order['id']}/confirm-received").status_code, 409)
        self.assertEqual(seller.get("/api/wallet").json["balance"], "95.00")
        self.assertEqual(self.post(buyer, f"/api/orders/{order['id']}/refund").status_code, 409)

    def test_refund_returns_item_to_market(self):
        seller, buyer = self.signup("Ama Seller", "a@x.com"), self.signup("Kofi Buyer", "k@x.com")
        item = self.post(seller, "/api/items", data={"title": "Chair", "price": "20", "lat": "5.1", "lng": "-1.2"},
                         content_type="multipart/form-data").json
        ref = self.post(buyer, "/api/orders/checkout", json={"item_id": item["id"]}).json["checkout_url"].rsplit("/", 1)[-1]
        buyer.post(f"/payments/mock/{ref}/pay", data={"csrf_token": self._tok(buyer)}, follow_redirects=True)
        oid = buyer.get("/api/orders?role=buying").json[0]["id"]
        self.assertEqual(self.post(buyer, f"/api/orders/{oid}/refund").status_code, 200)
        self.assertEqual(len(buyer.get("/api/items").json), 1)
        self.assertEqual(seller.get("/api/wallet").json["balance"], "0.00")

    def test_csrf_and_auth(self):
        c = self.app.test_client()
        self.assertEqual(c.post("/api/auth/login", json={}).status_code, 400)
        self.assertEqual(c.get("/api/orders").status_code, 401)


if __name__ == "__main__":
    unittest.main()
