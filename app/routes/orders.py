from decimal import Decimal
from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import MenuItem, Order, TimeSlot
from app.services import order_service
from app.utils.timeutil import utcnow

bp = Blueprint("orders", __name__)

ERRORS = {
    "EMPTY_CART": "Your cart is empty.",
    "INVALID_SLOT": "Please choose a valid pickup slot.",
    "SLOT_FULL": "That slot is full. Pick another one.",
    "SLOT_TOO_SOON": "Kitchen needs 25 min prep — please pick a later slot.",
    "ITEM_UNAVAILABLE": "An item in your cart is unavailable or out of stock.",
    "GATEWAY_ERROR": "Payment service is unavailable. Please try again.",
    "NOT_FOUND": "Order not found.",
    "NOT_CANCELLABLE": "This order can no longer be cancelled.",
    "CANCEL_WINDOW_OVER": "The 5-minute free-cancel window has passed; the kitchen has started.",
}


def _cart():
    return session.setdefault("cart", {})


def _orderable_slots():
    """Only slots with enough lead time for the 25-min prep rule."""
    cutoff = utcnow() + timedelta(minutes=current_app.config.get("PREP_TIME_MINUTES", 25))
    return (TimeSlot.query.filter(TimeSlot.start_time > cutoff)
            .order_by(TimeSlot.start_time).all())


@bp.post("/cart/add/<int:item_id>")
@login_required
def cart_add(item_id):
    item = db.session.get(MenuItem, item_id) or abort(404)
    qty = max(1, min(request.form.get("qty", 1, type=int), 10))
    cart = _cart()
    cart[str(item.id)] = min(cart.get(str(item.id), 0) + qty, 10)
    session.modified = True
    flash(f"Added {item.name} to cart.", "success")
    return redirect(url_for("menu.index"))


@bp.post("/cart/remove/<int:item_id>")
@login_required
def cart_remove(item_id):
    _cart().pop(str(item_id), None)
    session.modified = True
    return redirect(url_for("orders.cart"))


@bp.get("/cart")
@login_required
def cart():
    lines, total = [], Decimal("0.00")
    for key, qty in _cart().items():
        item = db.session.get(MenuItem, int(key))
        if item:
            subtotal = item.price * qty
            lines.append({"item": item, "qty": qty, "subtotal": subtotal})
            total += subtotal
    slots = _orderable_slots()
    return render_template("orders/cart.html", lines=lines, total=total, slots=slots,
                           prep_minutes=current_app.config.get("PREP_TIME_MINUTES", 25))


@bp.post("/checkout")
@login_required
def checkout():
    cart_items = [{"item_id": int(k), "qty": v} for k, v in _cart().items()]
    result = order_service.place_order(current_user, cart_items,
                                       request.form.get("slot_id", type=int))
    if not result["success"]:
        flash(ERRORS.get(result["error"], "Could not place order."), "danger")
        return redirect(url_for("orders.cart"))
    session.pop("cart", None)
    return redirect(result["pay_url"])


@bp.get("/orders")
@login_required
def history():
    orders = (Order.query.filter_by(user_id=current_user.id)
              .order_by(Order.created_at.desc()).all())
    return render_template("orders/history.html", orders=orders)


@bp.get("/orders/<int:order_id>")
@login_required
def detail(order_id):
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    cancel_window = current_app.config.get("CANCEL_WINDOW_MINUTES", 5)
    grace = current_app.config.get("PICKUP_GRACE_MINUTES", 15)
    return render_template("orders/detail.html", order=order, cancel_window=cancel_window,
                           grace_minutes=grace)


@bp.get("/orders/<int:order_id>/status")
@login_required
def status_json(order_id):
    """Real-time polling endpoint for the tracking page (no full reload)."""
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    return jsonify(id=order.id, status=order.status.value,
                   token=order.token, total=float(order.total),
                   slot_start=order.slot.start_time.isoformat() if order.slot else None,
                   grace_minutes=current_app.config.get("PICKUP_GRACE_MINUTES", 15),
                   can_cancel=order.can_cancel(current_app.config.get("CANCEL_WINDOW_MINUTES", 5)))


@bp.post("/orders/<int:order_id>/cancel")
@login_required
def cancel(order_id):
    result = order_service.cancel_order(current_user, order_id)
    flash("Order cancelled." if result["success"] else ERRORS.get(result["error"], "Error"),
          "success" if result["success"] else "danger")
    return redirect(url_for("orders.history"))
