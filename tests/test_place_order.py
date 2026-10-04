"""Basis-path tests for order_service.place_order (cyclomatic complexity = 7)."""
from app import gateway
from app.extensions import db
from app.models import Order, OrderStatus, TimeSlot
from app.services import order_service


def cart(*pairs):
    return [{"item_id": i, "qty": q} for i, q in pairs]


def test_path1_empty_cart(app, user):
    assert order_service.place_order(user, [], 1)["error"] == "EMPTY_CART"


def test_path2_invalid_slot(app, user):
    assert order_service.place_order(user, cart((1, 1)), 99)["error"] == "INVALID_SLOT"


def test_path3_slot_full(app, user):
    assert order_service.place_order(user, cart((1, 1)), 2)["error"] == "SLOT_FULL"


def test_path4_item_unavailable(app, user):
    assert order_service.place_order(user, cart((3, 1)), 1)["error"] == "ITEM_UNAVAILABLE"


def test_path5_gateway_failure(app, user, monkeypatch):
    monkeypatch.setattr(gateway, "create_payment",
                        lambda oid, amt: gateway.PaymentResult(ok=False))
    result = order_service.place_order(user, cart((1, 2)), 1)
    assert result["error"] == "GATEWAY_ERROR"
    assert Order.query.one().status == OrderStatus.FAILED
    assert db.session.get(TimeSlot, 1).booked == 0


def test_path6_success_single_item(app, user):
    result = order_service.place_order(user, cart((1, 2)), 1)
    assert result["success"] and float(result["total"]) == 80.0
    order = Order.query.one()
    assert order.status == OrderStatus.PENDING_PAYMENT
    assert order.payment.gateway_ref in result["pay_url"]


def test_path7_success_multiple_items(app, user):
    result = order_service.place_order(user, cart((1, 1), (2, 2)), 1)
    assert result["success"] and float(result["total"]) == 70.0
    assert len(Order.query.one().items) == 2
