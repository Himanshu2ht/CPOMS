"""Startup self-healing: recreate demo data when the database is empty.

The hosted (Render + Supabase) database starts completely empty — no users, no
menu, no slots — so the app shows only the customer UI and there is no admin
or staff account to log in with. This module fills a FRESH database
automatically on boot, exactly like `seed.py` does locally.

Safety rules:
- NEVER deletes anything. It only inserts, and only when the users table is
  empty (fresh DB). A database that already has users is left untouched.
- NEVER runs in tests (TESTING=True skips it).
- NEVER crashes startup: any error is logged and boot continues.
"""
import logging
from datetime import timedelta

log = logging.getLogger(__name__)

MENU = [("Veg Sandwich", "Snacks", 40, 50), ("Samosa (2 pcs)", "Snacks", 20, 80),
        ("Masala Dosa", "Meals", 60, 40), ("Chole Bhature", "Meals", 70, 30),
        ("Masala Chai", "Beverages", 15, 100), ("Cold Coffee", "Beverages", 40, 60)]

USERS = [("Admin", "admin@college.edu", "admin"),
         ("Kitchen Staff", "staff@college.edu", "staff"),
         ("Demo Student", "student@college.edu", "customer")]

DEFAULT_PASSWORD = "Password@123"  # change after first login via /profile


def ensure_demo_data():
    """Seed demo users/menu/slots/categories iff the users table is empty."""
    from app.extensions import db
    from app.models import Category, MenuItem, TimeSlot, User
    from app.utils.timeutil import utcnow

    if User.query.first() is not None:
        return False  # lived-in DB: do nothing
    for name, email, role in USERS:
        user = User(name=name, email=email, role=role)
        user.set_password(DEFAULT_PASSWORD)
        db.session.add(user)
    for n, c, p, s in MENU:
        db.session.add(MenuItem(name=n, category=c, price=p, stock=s))
    for c in {c for _, c, _, _ in MENU}:
        if not Category.query.filter_by(name=c).first():
            db.session.add(Category(name=c))
    base = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for i in range(6):
        db.session.add(TimeSlot(start_time=base + timedelta(minutes=15 * i), capacity=20))
    db.session.commit()
    log.warning("Database was empty: seeded demo users, menu and slots "
                "(admin@college.edu / Password@123 — change after login).")
    return True


def safe_ensure_demo_data():
    try:
        return ensure_demo_data()
    except Exception as exc:  # noqa: BLE001 - seeding must never crash boot
        from app.extensions import db

        db.session.rollback()
        log.warning("Auto-seed skipped (%s).", exc)
        return False
