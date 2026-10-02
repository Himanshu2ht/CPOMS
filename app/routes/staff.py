from datetime import timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import MenuItem, Order, OrderStatus
from app.services import order_service
from app.utils.decorators import role_required
from app.utils.timeutil import utcnow

bp = Blueprint("staff", __name__, url_prefix="/staff")

NEXT_ACTION = {OrderStatus.PAID: OrderStatus.PREPARING,
               OrderStatus.PREPARING: OrderStatus.READY}

ACTIVE = (OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.READY)


def _queue_orders():
    return (Order.query.filter(Order.status.in_(list(ACTIVE)))
            .order_by(Order.slot_id, Order.created_at).all())


@bp.get("/")
@role_required("staff", "admin")
def dashboard():
    """Staff dashboard: live KPIs + kitchen queue + low-stock + no-show alerts."""
    order_service.sweep_no_shows()  # auto-resolve stale READY orders on each visit
    orders = _queue_orders()
    counts = {s.value: sum(1 for o in orders if o.status == s) for s in ACTIVE}
    overdue = [o for o in orders if o.is_pickup_overdue(
        current_app.config.get("PICKUP_GRACE_MINUTES", 60))]
    low_stock = (MenuItem.query.filter(MenuItem.stock <= 5)
                 .order_by(MenuItem.stock).limit(10).all())
    no_shows_today = Order.query.filter(
        Order.status == OrderStatus.NO_SHOW,
        Order.created_at > utcnow() - timedelta(hours=24)).count()
    return render_template("staff/dashboard.html", orders=orders, counts=counts,
                           next_action=NEXT_ACTION, overdue=overdue,
                           low_stock=low_stock, no_shows_today=no_shows_today)


@bp.get("/queue")
@role_required("staff", "admin")
def queue():
    orders = _queue_orders()
    return render_template("staff/queue.html", orders=orders, next_action=NEXT_ACTION)


@bp.get("/queue-data")
@role_required("staff", "admin")
def queue_data():
    """Real-time polling endpoint for the kitchen display (JSON, no reload)."""
    orders = _queue_orders()
    return jsonify([{
        "id": o.id, "token": o.token, "customer": o.user.name,
        "slot": o.slot.start_time.isoformat() if o.slot else None,
        "items": [f"{l.quantity}x {l.item.name}" for l in o.items],
        "status": o.status.value,
        "overdue": o.is_pickup_overdue(current_app.config.get("PICKUP_GRACE_MINUTES", 60)),
    } for o in orders])


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


@bp.post("/orders/<int:order_id>/no-show")
@role_required("staff", "admin")
def mark_no_show(order_id):
    """Manual no-pickup handling: READY order the customer never collected."""
    order = db.session.get(Order, order_id)
    result = order_service.advance_status(order, OrderStatus.NO_SHOW) if order else {"success": False}
    flash("Marked as no-show (logged for waste report)." if result.get("success")
          else "Only READY orders can be marked no-show.", "success" if result.get("success") else "danger")
    return redirect(url_for("staff.dashboard" if request.form.get("from") == "dashboard" else "staff.queue"))


@bp.post("/sweep-no-shows")
@role_required("staff", "admin")
def sweep():
    n = order_service.sweep_no_shows()
    flash(f"{n} overdue pickup(s) marked as no-show.", "info")
    return redirect(url_for("staff.dashboard"))
