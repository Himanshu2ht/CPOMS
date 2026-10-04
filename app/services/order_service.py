"""Order placement, cancellation and status workflow."""
from datetime import timedelta
from decimal import Decimal

from flask import current_app

from app import gateway
from app.extensions import db
from app.models import (MenuItem, Order, OrderItem, OrderStatus, Payment,
                        PaymentStatus, TimeSlot)
from app.utils.timeutil import utcnow

from . import payment_service
from .result import fail, ok

ALLOWED_TRANSITIONS = {
    OrderStatus.PAID: {OrderStatus.PREPARING},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.COLLECTED, OrderStatus.NO_SHOW},
}


def _prep_minutes():
    try:
        return int(current_app.config.get("PREP_TIME_MINUTES", 25))
    except RuntimeError:  # outside app context (unit tests calling directly)
        return 25


def _cancel_window():
    try:
        return int(current_app.config.get("CANCEL_WINDOW_MINUTES", 5))
    except RuntimeError:
        return 5


def _grace_minutes():
    try:
        return int(current_app.config.get("PICKUP_GRACE_MINUTES", 15))
    except RuntimeError:
        return 15


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
    # 25-min prep rule: kitchen needs lead time, so reject near-term slots.
    if slot.start_time < utcnow() + timedelta(minutes=_prep_minutes()):
        return fail("SLOT_TOO_SOON")

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
    # 5-minute cancel window for PAID orders (then kitchen has started).
    if order.status == OrderStatus.PAID:
        if not order.can_cancel(_cancel_window()):
            return fail("CANCEL_WINDOW_OVER")
        return payment_service.refund(order)
    return fail("NOT_CANCELLABLE")


def advance_status(order, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        return fail("INVALID_TRANSITION")
    order.status = new_status
    db.session.commit()
    return ok(order_id=order.id, status=new_status.value)


def sweep_no_shows(grace_minutes=None):
    """Mark READY orders past slot+grace as NO_SHOW (the 'what if no pickup' answer).

    Returns number of orders flipped. Staff/admin can also do it manually per order.
    Food from NO_SHOW orders is logged for waste tracking (see admin dashboard).
    """
    grace = grace_minutes if grace_minutes is not None else _grace_minutes()
    cutoff = utcnow() - timedelta(minutes=grace)
    stale = (Order.query.join(TimeSlot, Order.slot_id == TimeSlot.id)
             .filter(Order.status == OrderStatus.READY,
                     TimeSlot.start_time < cutoff).all())
    for order in stale:
        order.status = OrderStatus.NO_SHOW
    db.session.commit()
    return len(stale)


def rollover_slots():
    """Keep daily slots date-agnostic: past slots with no live orders roll forward.

    Slots repeat every day at the same time, so a slot whose time passed today
    (and has no PENDING/PAID/PREPARING/READY orders attached) is pushed forward
    day-by-day until future, with its booking counter reset for the fresh day.
    Returns number of slots rolled.
    """
    now = utcnow()
    live = (OrderStatus.PENDING_PAYMENT, OrderStatus.PAID,
            OrderStatus.PREPARING, OrderStatus.READY)
    rolled = 0
    for slot in TimeSlot.query.all():
        if slot.start_time >= now:
            continue
        busy = Order.query.filter(Order.slot_id == slot.id,
                                  Order.status.in_(live)).first()
        if busy:
            continue
        while slot.start_time < now:
            slot.start_time += timedelta(days=1)
        slot.booked = 0
        rolled += 1
    if rolled:
        db.session.commit()
    return rolled
