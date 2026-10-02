"""Payment events: success, failure, refund, expiry. Idempotent by design."""
from datetime import timedelta

from app.extensions import db
from app.models import MenuItem, Order, OrderStatus, Payment, PaymentStatus
from app.utils.timeutil import utcnow

from .result import fail, ok


def _release_slot(order):
    if order.slot and order.slot.booked > 0:
        order.slot.booked -= 1


def handle_event(ref, success):
    """Apply a gateway result (from webhook or sandbox checkout) to an order."""
    payment = Payment.query.filter_by(gateway_ref=ref).first()
    if payment is None:
        return fail("UNKNOWN_PAYMENT")
    if payment.status != PaymentStatus.CREATED:      # duplicate webhook: ignore
        return ok(duplicate=True, order_id=payment.order_id)

    order = payment.order
    if order.status != OrderStatus.PENDING_PAYMENT:  # e.g. already expired
        return fail("ORDER_NOT_PAYABLE")

    if success:
        payment.status = PaymentStatus.SUCCESS
        payment.paid_at = utcnow()
        order.status = OrderStatus.PAID
        order.token = f"T{order.id:04d}"
        for line in order.items:                      # reduce stock only once paid
            item = db.session.get(MenuItem, line.item_id)
            item.stock = max(0, item.stock - line.quantity)
    else:
        payment.status = PaymentStatus.FAILED
        order.status = OrderStatus.FAILED
        _release_slot(order)
    db.session.commit()
    return ok(order_id=order.id, status=order.status.value)


def refund(order):
    """Full refund for a PAID order cancelled before preparation."""
    if order.status != OrderStatus.PAID:
        return fail("NOT_REFUNDABLE")
    order.payment.status = PaymentStatus.REFUNDED   # real gateway refund call goes here
    order.status = OrderStatus.CANCELLED
    for line in order.items:
        line.item.stock += line.quantity
    _release_slot(order)
    db.session.commit()
    return ok(order_id=order.id)


def expire_stale_orders(minutes):
    """Fail unpaid orders older than `minutes` and free their slots."""
    cutoff = utcnow() - timedelta(minutes=minutes)
    stale = Order.query.filter(Order.status == OrderStatus.PENDING_PAYMENT,
                               Order.created_at < cutoff).all()
    for order in stale:
        order.status = OrderStatus.FAILED
        if order.payment:
            order.payment.status = PaymentStatus.FAILED
        _release_slot(order)
    db.session.commit()
    return len(stale)
