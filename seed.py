"""Create demo users, menu and today's time slots:  python seed.py"""
from datetime import timedelta

from app import create_app
from app.extensions import db
from app.models import MenuItem, TimeSlot, User
from app.utils.timeutil import utcnow

app = create_app()

with app.app_context():
    if not User.query.filter_by(email="admin@college.edu").first():
        for name, email, role in [("Admin", "admin@college.edu", "admin"),
                                  ("Kitchen Staff", "staff@college.edu", "staff"),
                                  ("Demo Student", "student@college.edu", "customer")]:
            user = User(name=name, email=email, role=role)
            user.set_password("Password@123")        # change after first login
            db.session.add(user)
        menu = [("Veg Sandwich", "Snacks", 40, 50), ("Samosa (2 pcs)", "Snacks", 20, 80),
                ("Masala Dosa", "Meals", 60, 40), ("Chole Bhature", "Meals", 70, 30),
                ("Masala Chai", "Beverages", 15, 100), ("Cold Coffee", "Beverages", 40, 60)]
        for n, c, p, s in menu:
            db.session.add(MenuItem(name=n, category=c, price=p, stock=s))
        base = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        for i in range(6):
            db.session.add(TimeSlot(start_time=base + timedelta(minutes=15 * i), capacity=20))
        db.session.commit()
        print("Seeded. Login: admin@college.edu / Password@123")
    else:
        print("Already seeded.")
