"""Batch C part 2: Chapters 9-10 (tests, conclusion) + Chapters 12-13 (install, manuals, viva, history)."""
from docx import Document

P = "docs/CPOMS_Project_Report.docx"
d = Document(P)
paras = d.paragraphs


def sub_para(i, old, new):
    p = paras[i]
    assert old in p.text, f"[para {i}] not found: {old[:60]!r}"
    p.text = p.text.replace(old, new)


def set_para(i, text):
    paras[i].text = text


# ---- Ch.9: suite size + strategy + example + takeaway ----
sub_para(236, "full suite in Appendix B runs 22 cases FR→TC", "full suite in Appendix B runs 19 cases FR→TC")
set_para(237, "Pytest strategy: service functions are tested directly (basis paths P1–P7 for place_order: empty cart, bad slot, full slot, unavailable item, gateway failure, two success shapes) and end-to-end through the Flask test client (register → cart → checkout → sandbox pay → kitchen advance → token handover); the gateway is monkeypatched for failure paths, and webhooks are exercised with real HMAC signatures for both rejection and idempotency. SQLite in-memory stands in for MySQL/Postgres through the very same models. Example test names: test_webhook_signature_and_idempotency, test_cancel_paid_order_refunds, test_cannot_cancel_after_preparing, test_customer_cannot_open_staff_pages — each maps to an FR above, closing the traceability loop FR → UC → SEQ → Code → TC.")
set_para(238, "Example Pytest (runs as-is, sandbox gateway)  def test_webhook_signature_and_idempotency(client, app): place an order, build the webhook body, post with a wrong signature → 400; post with the real signature → 200 and Paid; post the same body again → duplicate: True, and stock dropped exactly once.")
sub_para(239, "8 basis paths + 12 functional cases. Online-only is tested at UI (no option), API (400 on cash), logic (HMAC+idempotency), and DB (UNIQUE txn) — defence in depth, verified.",
         "8 basis paths + 12 selected functional cases (19 automated in total). Online-only is tested at UI (no cash option exists), routes (role blocks return 403), logic (HMAC verify + idempotency on the gateway reference), and services (unpaid expiry, the 5-minute refund window) — defence in depth, verified.")

# ---- functional table 37: 12 rows mirroring the real suite ----
t37 = d.tables[37]
rows37 = [
 ("TC-01", "Register + login", "Ravi / Strong@1234", "Account created; hash differs from plaintext; login greets Ravi"),
 ("TC-02", "Short password rejected", "name X / 123", "Stays on register with the 8+ characters message"),
 ("TC-03", "Wrong password", "asha@college.edu / nope", "'Invalid email or password'; no session created"),
 ("TC-04", "Open redirect blocked", "login?next=//evil.com", "Redirect never leaves the site"),
 ("TC-05", "Customer locked out of staff/admin", "customer GETs /staff/queue, /admin/reports", "403 both times"),
 ("TC-06", "Happy path to handover", "cart → pay → staff advance ×2 → token verify", "PAID → PREPARING → READY → COLLECTED"),
 ("TC-07", "Failed payment frees slot", "sandbox checkout → Simulate failure", "Order FAILED; slot booked back to 0"),
 ("TC-08", "Webhook signature + idempotency", "bad sig → good sig → repeat", "400, then 200, then duplicate: True; stock cut once"),
 ("TC-09", "Cancel Paid refunds", "cancel seconds after paying", "CANCELLED; payment REFUNDED; stock restored"),
 ("TC-10", "No cancel after Preparing", "staff advances, then customer cancels", "Order stays PREPARING"),
 ("TC-11", "place_order basis paths", "P1 empty … P4 unavailable", "EMPTY_CART / INVALID_SLOT / SLOT_FULL / ITEM_UNAVAILABLE"),
 ("TC-12", "Gateway failure path", "create_payment stubbed to fail", "GATEWAY_ERROR; order FAILED; slot released"),
]
for i, (a, b, c, e) in enumerate(rows37, start=1):
    r = t37.rows[i]
    r.cells[0].text, r.cells[1].text, r.cells[2].text, r.cells[3].text = a, b, c, e

# ---- Ch.10 ----
sub_para(243, "a modest, well-scoped Flask + MySQL web app can dissolve",
         "a modest, well-scoped Flask + MySQL/PostgreSQL web app can dissolve")
sub_para(243, "refunds are automatic and auditable, and the manager finally gets slot-wise demand data instead of guesses.",
         "refunds are simulated against the sandbox adapter and recorded, and the manager finally gets slot-wise demand data instead of guesses.")
sub_para(248, "Pytest docs; Git/GitHub flow guides.",
         "Pytest docs; Git/GitHub flow guides; Render, Supabase and Gunicorn docs (deployment).")
sub_para(252, "The lab must run P1–P8 with the fake gateway plus TC-07 (cash tamper) before Demo 2 is accepted — the manager signs only when duplicate-ignored and cash-rejected both pass in front of witnesses.",
         "The lab must run P1–P8 plus the signature and idempotency tests before Demo 2 is accepted — the manager signs only when duplicate-ignored and forged-callback-rejected both pass in front of witnesses.")
sub_para(254, "v2.0 (current): online-only enforced in FR/DFD/schema/code/tests; slot caps added; 15-min hold added after stakeholder asked what stops cart-blocking.",
         "v2.0 (current): online-only enforced in FR/DFD/schema/code/tests; slot caps added; 15-min hold added after stakeholder asked what stops cart-blocking. v2.1 (this build): daily time-only slots with rollover, staff/admin dashboards, live polling plus countdowns, categories table, Users & Staff page, 5-minute cancel and 15-minute no-show rules, Render + Supabase deployment, 19-test suite green.")
sub_para(257, "and remember: no cash at the counter, only QRs. —",
         "and remember: no cash at the counter, only tokens. —")
sub_para(258, "Award full marks only if cash-rejected and duplicate-ignored are demonstrated live.",
         "Award full marks only if forged-callback-rejected and duplicate-ignored are demonstrated live.")

# ---- Ch.12 install guide + workbench note ----
set_para(287, "Prerequisites: Python 3.11+, Git, VS Code; MySQL 8 plus MySQL Workbench if you want local practice. Steps: (1) git clone <repo> and enter it; (2) python -m venv venv and activate it (Windows: venv\\Scripts\\activate); (3) pip install -r requirements.txt; (4) copy .env.example to .env and set SECRET_KEY, DATABASE_URL (MySQL locally) and PAYMENT_WEBHOOK_SECRET; (5) python seed.py — demo logins are admin, staff and student @college.edu with password Password@123; (6) python run.py and open http://127.0.0.1:5000; (7) pytest -q and expect 19 passed (SQLite in-memory, no database needed). Hosted instead: create a free Supabase Postgres project, paste its connection string as DATABASE_URL on Render (write %40 wherever the password contains @), deploy with gunicorn run:app — tables and demo data build themselves on first boot, then check /health/db. Never commit .env; rotate secrets each semester.")
sub_para(288, "Backup before each sprint demo: mysqldump -u cpoms -p cpoms > backup_sprintN.sql.",
         "Backup before each sprint demo: Supabase dashboard → Backups in production, or mysqldump -u cpoms -p cpoms > backup_sprintN.sql in the lab.")

# ---- user manual (one page per role) ----
set_para(290, "Student (2-minute flow): open the site → Register/Login (email plus a strong password) → Menu (instant search, stock badges) → Add to cart → Choose a daily slot (seats-left shown; the kitchen needs 25 minutes, so near slots are hidden) → Pay Online in the sandbox checkout (no cash option exists anywhere) → See confirmation with token, timeline and countdown → Arrive in the slot → Show the token → Collect. If payment fails, retry at once; unpaid orders lapse after 10 minutes and free the slot. Cancelling is free while unpaid, or within 5 minutes when Paid. Change passwords under Profile — never share them.")
set_para(291, "Kitchen staff: keep the display plugged in. New Paid orders arrive with live countdowns, sorted by slot then time — the table refreshes every 10 seconds and the action buttons never disappear. Tap Mark Preparing when cooking starts, Mark Ready when the tray is up. Type the token at handover (the box capitalises it by itself); wrong tokens are rejected on the spot. Mark No-Show for Ready orders nobody collects, or let the 15-minute grace sweep do it for you. If Wi-Fi drops, serve from memory and enter the transitions when back online — the database remains the truth.")
set_para(292, "Collection desk: ask for the token (for example T0012) → type it into Hand Over → the screen confirms the customer by name. Hand over only when the status is Ready — the form refuses anything else, and an already-collected token errors instead of handing twice. Never accept cash — point at Pay Online on the student's phone.")
set_para(293, "Manager (morning routine, 10 min): Admin Dashboard (revenue, active orders, low stock) → Menu (add items, set stock, toggle availability, add categories with or without items) → Slots (create daily times such as 12:30 with caps; past ones roll forward alone) → Users & Staff (promote staff, remove empty accounts) → Reports (sales, top items, no-show log). Menu and slot changes apply immediately.")
sub_para(294, "Hold expires in 15 min — retry quickly", "Unpaid orders lapse after 10 min — retry quickly")

# ---- DDL note + viva + history ----
sub_para(300, "Full .sql file lives in /db/schema.sql and is attached in Appendix D.",
         "At runtime SQLAlchemy create_all is the source of truth and an empty database seeds itself — the Workbench file is the design record. Full .sql lives in /db/schema.sql and is attached in Appendix D.")
t44 = d.tables[44]
for r in t44.rows[1:]:
    q = r.cells[0].text.strip()
    if q.startswith("Duplicate charge?"):
        r.cells[1].text = "UNIQUE gateway_ref + idempotent confirm → idempotency test proves one Paid per ref → §7.4, §9."
    elif q.startswith("Slot full?"):
        r.cells[1].text = "Atomic booked counter + 25-min lead; SLOT_FULL / SLOT_TOO_SOON asks for another slot → FR-05."
    elif q.startswith("Refund to cash?"):
        r.cells[1].text = "Never — sandbox refund to source only, history kept → FR-14."
    elif q.startswith("Security?"):
        r.cells[1].text = "Werkzeug scrypt hash, 5-fail lockout, CSRF, HMAC, roles, browser-close sessions → §4.5."
sub_para(308, "walk in with the QR demo on your phone. Good luck.",
         "walk in with the token demo on your phone. Good luck.")
sub_para(309, "Next: v2.1 after UAT (slot-item caps, WebSocket option).",
         "Next: v2.1 after UAT (slot-item caps, WebSocket option) — shipped as daily slots, dashboards, countdowns, categories, no-show rules and Render/Supabase hosting.")

d.save(P)
print("Batch C2 saved.")
