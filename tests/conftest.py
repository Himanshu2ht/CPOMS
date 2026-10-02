from datetime import timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import MenuItem, TimeSlot, User
from app.utils.timeutil import utcnow
from config import TestConfig


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        for name, email, role in [("Asha", "asha@college.edu", "customer"),
                                  ("Kiran", "staff@college.edu", "staff"),
                                  ("Admin", "admin@college.edu", "admin")]:
            u = User(name=name, email=email, role=role)
            u.set_password("Password@123")
            db.session.add(u)
        db.session.add_all([
            MenuItem(name="Veg Sandwich", price=40, stock=10),     # id 1
            MenuItem(name="Masala Chai", price=15, stock=20),      # id 2
            MenuItem(name="Samosa", price=20, stock=0),            # id 3 (out of stock)
            TimeSlot(start_time=utcnow() + timedelta(hours=1), capacity=5, booked=0),   # id 1
            TimeSlot(start_time=utcnow() + timedelta(hours=2), capacity=1, booked=1),   # id 2 (full)
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user(app):
    return User.query.filter_by(email="asha@college.edu").first()


def login(client, email="asha@college.edu", password="Password@123"):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)
