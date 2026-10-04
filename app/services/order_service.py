"""Order placement, cancellation and status workflow."""
from decimal import Decimal

from app import gateway
from app.extensions import db
from app.models import (MenuItem, Order, OrderItem, OrderStatus, Payment,
                        PaymentStatus, TimeSlot)

from . import payment_service
from .result import fail, ok

ALLOWED_TRANSITIONS = {
    OrderStatus.PAID: {OrderStatus.PREPARING},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.COLLECTED},
}


def is_orderable(item, qty):
    """An item can be ordered if it exists, is switched on and has stock."""
    return item is not None and item.is_available and item.stock >= qty


def create_order(user, slot, lines, total):
    order = Order(user_id=user.id, slot_id=slot.id, total=total,
                  status=OrderStatus.PENDING_PAYMENT)
    for item, qty in lines:
        order.items.append(OrderItem(item_id=item.id, quantity=qty,
                                     unit_price=item.price))
    slot.booked += 1
    db.session.add(order)
    db.session.commit()
    return order


def place_order(user, cart, slot_id):
    """Validate a cart, create a PENDING_PAYMENT order and start online payment.

    cart = [{"item_id": 1, "qty": 2}, ...]
    This is the module analysed with basis-path testing (cyclomatic complexity 7).
    """
    if not cart:                                              # P1
        return fail("EMPTY_CART")
    slot = db.session.get(TimeSlot, slot_id)
    if slot is None:                                          # P2
        return fail("INVALID_SLOT")
    if slot.booked >= slot.capacity:                          # P3
        return fail("SLOT_FULL")

    total = Decimal("0.00")
    lines = []
    for entry in cart:                                        # P4
        item = db.session.get(MenuItem, entry["item_id"])
        if not is_orderable(item, entry["qty"]):              # P5
            return fail("ITEM_UNAVAILABLE")
        total += item.price * entry["qty"]
        lines.append((item, entry["qty"]))

    order = create_order(user, slot, lines, total)
    payment = gateway.create_payment(order.id, total)
    if not payment.ok:                                        # P6
        order.status = OrderStatus.FAILED
        slot.booked -= 1
        db.session.commit()
        return fail("GATEWAY_ERROR")

    db.session.add(Payment(order_id=order.id, gateway_ref=payment.ref,
                           amount=total, status=PaymentStatus.CREATED))
    db.session.commit()
    return ok(order_id=order.id, pay_url=payment.url, total=total)


def cancel_order(user, order_id):
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != user.id:
        return fail("NOT_FOUND")
    if order.status == OrderStatus.PENDING_PAYMENT:
        order.status = OrderStatus.CANCELLED
        if order.payment:
            order.payment.status = PaymentStatus.FAILED
        order.slot.booked = max(0, order.slot.booked - 1)
        db.session.commit()
        return ok(order_id=order.id)
    if order.status == OrderStatus.PAID:                      # refundable window
        return payment_service.refund(order)
    return fail("NOT_CANCELLABLE")


def advance_status(order, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        return fail("INVALID_TRANSITION")
    order.status = new_status
    db.session.commit()
    return ok(order_id=order.id, status=new_status.value)
