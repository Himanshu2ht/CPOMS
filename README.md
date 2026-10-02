# Canteen Pre-Order & Order Management System

Flask + MySQL web app: students/staff pre-order food, **pay online only**, pick a time slot,
track status and collect with a pickup token. Staff run a live kitchen queue; admin manages menu,
slots and reports.

## Setup
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then edit the values
# MySQL Workbench / CLI:
#   CREATE DATABASE canteen_db CHARACTER SET utf8mb4;
#   CREATE USER 'canteen_user'@'localhost' IDENTIFIED BY 'StrongPassword';
#   GRANT ALL ON canteen_db.* TO 'canteen_user'@'localhost';
python seed.py          # demo users, menu, slots (admin@college.edu / Password@123)
python run.py           # http://127.0.0.1:5000
pytest -q               # 18 tests (SQLite in-memory)
```

Or with Docker (real MySQL, no local install):
```bash
docker compose up --build   # web on :5000, mysql on :3306, health at /health/db
```

## Roles
| Role | Can do |
|------|--------|
| customer | browse menu, cart, pick slot, pay online, track/cancel orders, profile |
| staff | kitchen dashboard + queue (live), advance status, verify pickup token, mark no-show, manage stock |
| admin | everything above + admin dashboard, time slots, reports + waste log, expire unpaid |

## Business rules (tunable in `.env`)
| Rule | Default | Meaning |
|------|---------|---------|
| `PREP_TIME_MINUTES` | 25 | slots < 25 min away are hidden & rejected (`SLOT_TOO_SOON`) |
| `CANCEL_WINDOW_MINUTES` | 5 | PAID orders refundable only within 5 min; PENDING always free |
| `PICKUP_GRACE_MINUTES` | 60 | READY past slot+60 min → `NO_SHOW` (auto-sweep + manual button, no refund) |
| `PAYMENT_TIMEOUT_MINUTES` | 10 | unpaid orders expire after this |

## Real-time updates
No page reloads needed: order page polls `GET /orders/<id>/status` every 8s
(timeline + badge update live); kitchen polls `GET /staff/queue-data` every 10s
(counts + rows). Admin charts use `GET /admin/reports-data`.

## Authentication (how user profiles work)
- **Storage:** `users(name, email unique, password_hash, role)`. Passwords hashed with
  werkzeug scrypt (`set_password`/`check_password`) — never plain text.
- **Session:** Flask-Login signed cookie (`HttpOnly`, `SameSite=Lax`, `Secure` behind HTTPS),
  `session_protection="strong"`, no persistent remember-me, open-redirect guard on `next`.
- **Policy:** 8+ chars with upper + lower + digit + special; login rate-limited
  (5 fails / 5 min per IP+email); roles are admin-assigned, users edit only name/password
  at `/profile`.
- Demo logins (password `Password@123`): `admin@college.edu`, `staff@college.edu`, `student@college.edu`.

## Database connectivity
`DATABASE_URL` (MySQL via PyMySQL, `pool_pre_ping`) is primary; if MySQL is unreachable
and `DB_FALLBACK_SQLITE=1`, the app falls back to `instance/canteen.db` instead of crashing.
`GET /health/db` reports `{ok, backend}` — used by the admin dashboard badge and by
`docker compose` healthchecks.

## Payment
`app/gateway.py` is a sandbox adapter (HMAC-signed webhook, hosted-checkout style page).
Swap `create_payment()` for the real gateway SDK (e.g. Razorpay) to go live.
Orders are confirmed only after a successful payment event; stock is reduced then.
<<<<<<< HEAD

## Git (reversing mistakes)
```bash
git log --oneline          # baseline: "before fixes", then one commit per fix
git diff HEAD~1            # see what the last change did
git revert <commit>        # undo a bad change safely (keeps history)
git reset --hard HEAD~1    # ⚠️ throw away last commit (use only locally)
```


....

