# Marketplace (buy / sell / explore, location-based, escrow payments)

## Layers (top = what the user touches, bottom = storage)

| # | Layer | Folder | Responsibility |
|---|-------|--------|----------------|
| 6 | Presentation | `app/templates`, `app/static` | HTML pages, `app.js` calls the JSON API, browser geolocation |
| 5 | Routes (HTTP) | `app/routes` | Parse request, call a service, return JSON/HTML. No business rules |
| 4 | Services | `app/services` | All rules: signup, listing, nearby search, escrow state machine |
| 3 | Gateways | `app/gateways` | Payment provider adapters (`mock`, `paystack`) |
| 2 | Repositories | `app/repositories` | Only SQL |
| 1 | Database | `app/db.py` | Connection, schema, distance function |
| 0 | Config | `app/config.py` | Environment variables |

Rule: a layer only calls the layer directly below it.

## Escrow flow
1. Buyer taps **Buy** -> order `PENDING_PAYMENT`, item `RESERVED` (nobody else can buy it).
2. Buyer pays -> we verify with the gateway ourselves -> order `ESCROW_HELD`. Money stays with the platform.
3. Seller marks **shipped** (optional).
4. Buyer taps **I received the item** -> order `COMPLETED`, seller wallet credited (price minus platform fee). Only the buyer can do this, and only once.
5. Before completion: buyer can refund while unshipped; seller can refund any time; buyer can **dispute** after shipping (funds freeze).

Unique IDs: items `ITM-XXXXXXXXXX`, orders `ORD-...`, users `USR-...`, payments `PAY-...`.

## Run locally (step by step)
1. Install Python 3.11+.
2. `cd marketplace`
3. `python -m venv venv`
4. Activate it: Windows `venv\Scripts\activate` / Mac-Linux `source venv/bin/activate`
5. `pip install -r requirements.txt`
6. `python run.py`
7. Open http://localhost:5000 (geolocation works on localhost).
8. Sign up two accounts (use a private window for the second), list an item with one, buy it with the other. The simulated checkout page appears.

## Run the tests
`python -m unittest discover -s tests -t . -v`

## Go live with real payments (Paystack, GHS)
1. Create a Paystack account, copy the **secret key** (Settings -> API Keys).
2. Set `PAYMENT_PROVIDER=paystack` and `PAYSTACK_SECRET_KEY=sk_...`.
3. In Paystack dashboard set the **webhook URL** to `https://YOUR-DOMAIN/payments/webhook/paystack`.
4. Test with Paystack test keys first, then switch to live keys.

## Deploy on Render (step by step)
1. Push this folder to a GitHub repository (`.env` is git-ignored; never commit keys).
2. On render.com: **New -> Blueprint** -> pick the repo. `render.yaml` creates the service, a 1 GB disk at `/data` (database + photos) and a random `SECRET_KEY`.
3. After deploy, open the `https://...onrender.com` URL (HTTPS is required for browser geolocation).
4. Add `PAYSTACK_SECRET_KEY` in the service's Environment tab when going live.
Any Docker host works the same way: `docker build -t market . && docker run -p 8000:8000 -v market-data:/data market`.
(Render's disks need a paid instance; free instances lose data on restart.)

## Known limits / next steps
- SQLite is fine for one server. For several servers, move to PostgreSQL (only `app/db.py` and `app/repositories` change).
- Payout from seller wallet to mobile money/bank (Paystack Transfers) and an admin screen to resolve disputes are not built; disputed funds stay frozen.
- Add auto-release/auto-refund timers and email notifications as needed.
