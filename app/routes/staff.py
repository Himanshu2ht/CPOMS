from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Order, OrderStatus
from app.services import order_service
from app.utils.decorators import role_required

bp = Blueprint("staff", __name__, url_prefix="/staff")

NEXT_ACTION = {OrderStatus.PAID: OrderStatus.PREPARING,
               OrderStatus.PREPARING: OrderStatus.READY}


@bp.get("/queue")
@role_required("staff", "admin")
def queue():
    orders = (Order.query
              .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.READY]))
              .order_by(Order.slot_id, Order.created_at).all())
    return render_template("staff/queue.html", orders=orders, next_action=NEXT_ACTION)


@bp.post("/orders/<int:order_id>/advance")
@role_required("staff", "admin")
def advance(order_id):
    order = db.session.get(Order, order_id)
    target = NEXT_ACTION.get(order.status) if order else None
    result = order_service.advance_status(order, target) if target else {"success": False}
    if not result["success"]:
        flash("That order cannot be moved forward.", "danger")
    return redirect(url_for("staff.queue"))


@bp.post("/verify")
@role_required("staff", "admin")
def verify_token():
    token = request.form.get("token", "").strip().upper()
    order = Order.query.filter_by(token=token, status=OrderStatus.READY).first()
    if order is None:
        flash("Token not found or order not ready.", "danger")
    else:
        order_service.advance_status(order, OrderStatus.COLLECTED)
        flash(f"Order {token} handed over to {order.user.name}.", "success")
    return redirect(url_for("staff.queue"))
