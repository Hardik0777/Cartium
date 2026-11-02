# Cartium

![CI](https://github.com/Hardik0777/Cartium/actions/workflows/ci.yml/badge.svg)

An AI-powered marketplace where **buyers** shop with multiple named carts, **sellers** run their own storefronts, and **admins** keep the platform healthy. Built with React + TypeScript, FastAPI and MySQL.

## Status

| Phase | Status |
|---|---|
| 1. Accounts: signup, login, JWT, buyer/seller/admin roles, seller approval state | ✅ Done |
| 2. Catalog: categories, search, filters, product pages, wishlist, recently viewed, reviews | ✅ Done |
| 3. Multiple named carts, saved addresses, Razorpay checkout, order tracking, reorder | ✅ Done |
| 4. Seller dashboard | ⏳ |
| 5. Admin dashboard | ⏳ |
| 6. Google sign-in | ⏳ |
| 7. AI shopping assistant (RAG) | ⏳ |
| 8. Deployment and docs | ⏳ |

## Run it locally (Windows)

**Requirements:** Python 3.12, Node.js 18+, MySQL 8.

### Backend

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend\.env`: put your MySQL root password in `DATABASE_URL` (if the password contains `@`, write it as `%40`), add your Razorpay **test** keys, and set `JWT_SECRET` (generate one with `py -3.12 -c "import secrets; print(secrets.token_hex(32))"`). Then:

```bash
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

`app.seed` creates the `cartium` database, its tables, and three demo accounts. API docs: http://127.0.0.1:8000/docs

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Demo accounts (local only)

| Role | Email | Password |
|---|---|---|
| Admin | admin@cartium.dev | Admin@123 |
| Seller (approved) | seller@cartium.dev | Seller@123 |
| Seller (approved) | home@cartium.dev | Seller@123 |
| Buyer | buyer@cartium.dev | Buyer@123 |
| Buyer | buyer2@cartium.dev | Buyer@123 |

The seed also adds 7 categories, 30 products and a few reviews. Brand names in the demo catalog are invented.

## How authentication works

- Passwords are hashed with **bcrypt**; the API never returns them.
- Login returns a **JWT** carrying the user id, role and a `token_version`.
- **Logout** increments `token_version`, so every earlier token stops working (all devices).
- Banned (deactivated) accounts are rejected on every request, not only at login.
- Role guards (`require_role`, `require_approved_seller`) protect routes on the server; the frontend mirrors them only for navigation.
- New sellers start as **pending** and can't sell until an admin approves them.
- Wrong password and unknown email return the same message, so emails can't be probed.

## Catalog design notes

- **Visibility in one place:** shoppers only ever see listings that an admin approved, from sellers who are active and approved. Catalog, wishlist and review queries all go through the same `visible_products()` query, so a suspended seller's products disappear everywhere at once.
- **Money as exact decimals:** prices are `DECIMAL(10,2)` in MySQL, never floats.
- **Cached ratings:** each product stores its average rating and review count, recalculated whenever a review is added, edited or deleted, so listing pages don't average reviews on every request.
- **Microsecond timestamps on MySQL:** MySQL's `DATETIME` keeps whole seconds by default, which made "recently viewed" order wrong when two products were opened within the same second. Timestamps use `DATETIME(6)`.
- **Safe search:** `%` and `_` in search terms are escaped, so they match literally instead of acting as wildcards.
- **Filters live in the URL,** so a filtered, sorted page can be bookmarked or shared.
- **Recently viewed** keeps the latest 20 products per user, with no duplicates.
- **Review privacy:** reviews show the reviewer's first name only.

## Checkout and payments

Razorpay test mode works end to end locally. Pay with Razorpay's test cards or test UPI ID (`success@razorpay`); no real money moves.

1. **Server-side totals.** The browser only sends which cart and which address. Prices, delivery fee and total are calculated from the database, and the amount sent to Razorpay is in paise.
2. **Stock is reserved when checkout starts**, under `SELECT ... FOR UPDATE` row locks taken in product-id order (so two checkouts can't deadlock). A test races two buyers for the last unit on real MySQL; exactly one wins. That test caught a real bug: SQLAlchemy was returning cached product rows instead of the values read under the lock (fixed with `populate_existing`).
3. **Payment is confirmed by signature.** Razorpay signs `order_id|payment_id` with the secret key; the server recomputes it with HMAC-SHA256 and compares in constant time. A forged signature is rejected.
4. **Reservations expire.** If the buyer closes the payment window, stock is returned immediately; unpaid checkouts are released after 15 minutes (cleaned up lazily, so no background job is needed).
5. **Orders are snapshots.** Item names, prices paid and the delivery address are copied onto the order, so later edits to a listing or address never change past orders.
6. **Per-item tracking.** Each seller ships their own items, so status (Placed, Packed, Shipped, Delivered) is tracked per item; the order shows the progress of its slowest item.
7. **Verifying twice is safe.** A double click or retry won't mark an order paid twice.

## Tests

```bash
cd backend
python -m pytest tests -q
```

Tests use a throwaway SQLite database by default. Set `TEST_DATABASE_URL` to run them against MySQL; **CI runs them on a real MySQL 8 server** on every push.

## Project structure

```
backend/
  app/
    core/          settings, password hashing, JWT
    dependencies/  auth and role guards
    routers/       API routes
    models.py      database tables
    schemas.py     request and response shapes
    seed.py        creates the database and demo accounts
  tests/
frontend/
  src/
    pages/         login, signup, account, seller hub, admin
    components/    layout, route guard, auth layout
    api.ts         API client
    auth.tsx       session handling
```
