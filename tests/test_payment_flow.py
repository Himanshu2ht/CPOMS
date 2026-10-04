import json

from app import gateway
from app.extensions import db
from app.models import MenuItem, Order, OrderStatus, PaymentStatus, TimeSlot
from tests.conftest import login


def _place(client):
    login(client)
    client.post("/cart/add/1", data={"qty": 2})
    r = client.post("/checkout", data={"slot_id": 1})
    assert r.status_code == 302 and "/payments/checkout/" in r.headers["Location"]
    return r.headers["Location"].rsplit("/", 1)[1]


def test_full_happy_path(client, app):
    ref = _place(client)
    client.post(f"/payments/checkout/{ref}/complete", data={"outcome": "success"})
    order = Order.query.one()
    assert order.status == OrderStatus.PAID and order.token == f"T{order.id:04d}"
    assert db.session.get(MenuItem, 1).stock == 8                 # stock reduced after payment
    # staff moves it through the kitchen workflow and hands it over
    login(client, "staff@college.edu")
    client.post(f"/staff/orders/{order.id}/advance")
    client.post(f"/staff/orders/{order.id}/advance")
    assert order.status == OrderStatus.READY
    client.post("/staff/verify", data={"token": order.token})
    assert order.status == OrderStatus.COLLECTED


def test_failed_payment_releases_slot(client, app):
    ref = _place(client)
    client.post(f"/payments/checkout/{ref}/complete", data={"outcome": "failure"})
    assert Order.query.one().status == OrderStatus.FAILED
    assert db.session.get(TimeSlot, 1).booked == 0


def test_webhook_signature_and_idempotency(client, app):
    ref = _place(client)
    body = json.dumps({"ref": ref, "status": "success"}).encode()
    bad = client.post("/payments/webhook", data=body, headers={"X-Signature": "wrong"})
    assert bad.status_code == 400
    sig = gateway.sign(body, app.config["PAYMENT_WEBHOOK_SECRET"])
    assert client.post("/payments/webhook", data=body, headers={"X-Signature": sig}).status_code == 200
    again = client.post("/payments/webhook", data=body, headers={"X-Signature": sig})
    assert again.get_json()["duplicate"] is True
    assert db.session.get(MenuItem, 1).stock == 8                 # stock reduced only once


def test_cancel_paid_order_refunds(client, app):
    ref = _place(client)
    client.post(f"/payments/checkout/{ref}/complete", data={"outcome": "success"})
    order = Order.query.one()
    client.post(f"/orders/{order.id}/cancel")
    assert order.status == OrderStatus.CANCELLED
    assert order.payment.status == PaymentStatus.REFUNDED
    assert db.session.get(MenuItem, 1).stock == 10                # stock restored


def test_cannot_cancel_after_preparing(client, app):
    ref = _place(client)
    client.post(f"/payments/checkout/{ref}/complete", data={"outcome": "success"})
    order = Order.query.one()
    login(client, "staff@college.edu")
    client.post(f"/staff/orders/{order.id}/advance")
    login(client)
    client.post(f"/orders/{order.id}/cancel")
    assert order.status == OrderStatus.PREPARING


def test_admin_pages_render(client):
    login(client, "admin@college.edu")
    for url in ("/admin/menu", "/admin/slots", "/admin/reports", "/staff/queue", "/"):
        assert client.get(url).status_code == 200
