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

## Roles
| Role | Can do |
|------|--------|
| customer | browse menu, cart, pick slot, pay online, track/cancel orders |
| staff | kitchen queue, advance status, verify pickup token, manage stock |
| admin | everything above + time slots, reports, expire unpaid orders |

## Payment
`app/gateway.py` is a sandbox adapter (HMAC-signed webhook, hosted-checkout style page).
Swap `create_payment()` for the real gateway SDK (e.g. Razorpay) to go live.
Orders are confirmed only after a successful payment event; stock is reduced then.
