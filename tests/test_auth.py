from app.models import User
from tests.conftest import login


def test_register_and_login(client, app):
    r = client.post("/register", data={"name": "Ravi", "email": "ravi@college.edu",
                                       "password": "Strong@1234"}, follow_redirects=True)
    assert b"Account created" in r.data
    with app.app_context():
        u = User.query.filter_by(email="ravi@college.edu").one()
        assert u.password_hash != "Strong@1234"            # hashed, never plain text
    assert b"Ravi" in login(client, "ravi@college.edu", "Strong@1234").data


def test_register_rejects_short_password(client):
    r = client.post("/register", data={"name": "X", "email": "x@c.edu", "password": "123"})
    assert b"8+ characters" in r.data


def test_wrong_password(client):
    assert b"Invalid email or password" in login(client, password="nope").data


def test_open_redirect_blocked(client):
    r = client.post("/login?next=//evil.com", data={"email": "asha@college.edu",
                    "password": "Password@123"})
    assert "evil.com" not in r.headers["Location"]


def test_customer_cannot_open_staff_pages(client):
    login(client)
    assert client.get("/staff/queue").status_code == 403
    assert client.get("/admin/reports").status_code == 403


def test_staff_cannot_open_admin_pages(client):
    login(client, "staff@college.edu")
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/slots").status_code == 403
    assert client.get("/admin/reports").status_code == 403
    assert client.get("/staff/queue").status_code == 200
    assert client.get("/admin/menu").status_code == 200
