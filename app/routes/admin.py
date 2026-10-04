from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func

from app.extensions import db
from app.models import Category, MenuItem, Order, OrderStatus, TimeSlot, User, all_category_names
from app.services import order_service, payment_service, report_service
from app.utils.decorators import role_required
from app.utils.timeutil import utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@role_required("admin")
def dashboard():
    """Admin dashboard: revenue, orders, slots, users, DB health, no-shows."""
    since = utcnow() - timedelta(hours=24)
    paid_states = [OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.READY,
                   OrderStatus.COLLECTED, OrderStatus.NO_SHOW]
    revenue_24h = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_(paid_states), Order.created_at > since).scalar() or 0
    orders_24h = Order.query.filter(Order.created_at > since).count()
    active = Order.query.filter(Order.status.in_(
        [OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.READY])).count()
    no_shows = Order.query.filter(Order.status == OrderStatus.NO_SHOW).count()
    users = User.query.count()
    low_stock = MenuItem.query.filter(MenuItem.stock <= 5).count()
    try:
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        db_ok, db_backend = True, "connected"
    except Exception:  # noqa: BLE001
        db_ok, db_backend = False, "unreachable"
    slots = TimeSlot.query.order_by(TimeSlot.start_time).limit(8).all()
    return render_template("admin/dashboard.html", revenue_24h=float(revenue_24h),
                           orders_24h=orders_24h, active=active, no_shows=no_shows,
                           users=users, low_stock=low_stock, db_ok=db_ok,
                           db_backend=db_backend, slots=slots,
                           sales=report_service.daily_sales(),
                           top=report_service.top_items())


@bp.route("/menu", methods=["GET", "POST"])
@role_required("admin", "staff")
def menu():
    if request.method == "POST":
        try:
            price = Decimal(request.form.get("price", "0"))
            stock = int(request.form.get("stock", "0"))
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "Snacks").strip() or "Snacks"
            if not name or price <= 0 or stock < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a name, a positive price and a valid stock.", "danger")
        else:
            db.session.add(MenuItem(name=name, price=price, stock=stock, category=category))
            _ensure_category(category)
            db.session.commit()
            flash("Menu item added.", "success")
        return redirect(url_for("admin.menu"))
    return render_template("admin/menu.html",
                           items=MenuItem.query.order_by(MenuItem.category, MenuItem.name).all(),
                           categories=all_category_names())


def _ensure_category(name):
    name = (name or "").strip()
    if name and not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name))
    return name


@bp.post("/menu/categories/add")
@role_required("admin")
def add_category():
    """Add a category on its own — no item required."""
    name = request.form.get("category", "").strip()
    if not name:
        flash("Type a category name first.", "danger")
    elif Category.query.filter_by(name=name).first():
        flash(f"Category '{name}' already exists.", "info")
    else:
        db.session.add(Category(name=name))
        db.session.commit()
        flash(f"Category '{name}' added.", "success")
    return redirect(url_for("admin.menu"))


@bp.post("/menu/<int:item_id>/update")
@role_required("admin", "staff")
def update_item(item_id):
    """Full edit: staff typically touch stock/availability; admin can rename/reprice too."""
    from flask_login import current_user

    item = db.session.get(MenuItem, item_id)
    if item:
        if current_user.role == "admin":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            try:
                price = Decimal(request.form.get("price", str(item.price)))
                if price <= 0:
                    raise ValueError
                item.price = price
            except (InvalidOperation, ValueError):
                flash("Price must be a positive number.", "danger")
                return redirect(url_for("admin.menu"))
            if name:
                item.name = name
            if category:
                item.category = category
                _ensure_category(category)
        item.stock = max(0, request.form.get("stock", item.stock, type=int))
        item.is_available = request.form.get("is_available") == "on"
        db.session.commit()
        flash("Menu item updated.", "success")
    return redirect(url_for("admin.menu"))


@bp.post("/menu/<int:item_id>/delete")
@role_required("admin")
def delete_item(item_id):
    item = db.session.get(MenuItem, item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
        flash(f"Deleted {item.name}.", "info")
    return redirect(url_for("admin.menu"))


@bp.get("/users")
@role_required("admin")
def users():
    """See every DB user: customers, staff, admins. Change roles / remove accounts."""
    all_users = User.query.order_by(User.role.desc(), User.name).all()
    return render_template("admin/users.html", users=all_users)


@bp.post("/users/<int:user_id>/role")
@role_required("admin")
def set_role(user_id):
    from flask_login import current_user

    user = db.session.get(User, user_id)
    role = request.form.get("role", "")
    if user is None or role not in ("customer", "staff", "admin"):
        flash("Invalid user or role.", "danger")
    elif user.id == current_user.id:
        flash("You cannot change your own role.", "danger")
    else:
        user.role = role
        db.session.commit()
        flash(f"{user.email} is now {role}.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/delete")
@role_required("admin")
def delete_user(user_id):
    from flask_login import current_user

    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "danger")
    elif user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
    elif Order.query.filter_by(user_id=user.id).first():
        flash("Cannot delete: user has orders on record.", "danger")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"Deleted {user.email}.", "info")
    return redirect(url_for("admin.users"))


@bp.get("/orders")
@role_required("admin")
def all_orders():
    """Admin sees ALL orders (every user), newest first."""
    status = request.args.get("status", "")
    q = Order.query.order_by(Order.created_at.desc()).limit(100)
    orders = q.all()
    if status:
        orders = [o for o in orders if o.status.value == status]
    return render_template("admin/orders.html", orders=orders, status=status,
                           statuses=[s.value for s in OrderStatus])


@bp.route("/slots", methods=["GET", "POST"])
@role_required("admin")
def slots():
    """Daily slots: time-only (no date) — the same times repeat every day."""
    if request.method == "POST":
        try:
            t = datetime.strptime(request.form["start_time"], "%H:%M").time()
            capacity = int(request.form["capacity"])
            if capacity < 1:
                raise ValueError
        except (KeyError, ValueError):
            flash("Enter a valid time and capacity.", "danger")
        else:
            start = utcnow().replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if start <= utcnow():
                start += timedelta(days=1)
            db.session.add(TimeSlot(start_time=start, capacity=capacity))
            db.session.commit()
            flash(f"Daily slot at {t.strftime('%I:%M %p')} created.", "success")
        return redirect(url_for("admin.slots"))
    return render_template("admin/slots.html", slots=TimeSlot.query.order_by(TimeSlot.start_time.desc()).limit(30).all())


@bp.post("/slots/<int:slot_id>/delete")
@role_required("admin")
def delete_slot(slot_id):
    slot = db.session.get(TimeSlot, slot_id)
    if slot is None:
        flash("Slot not found.", "danger")
    elif Order.query.filter_by(slot_id=slot.id).first():
        flash("Cannot delete: orders are booked in this slot.", "danger")
    else:
        db.session.delete(slot)
        db.session.commit()
        flash("Slot deleted.", "info")
    return redirect(url_for("admin.slots"))


@bp.get("/reports")
@role_required("admin")
def reports():
    return render_template("admin/reports.html",
                           sales=report_service.daily_sales(),
                           top=report_service.top_items(),
                           no_shows=Order.query.filter_by(status=OrderStatus.NO_SHOW)
                           .order_by(Order.created_at.desc()).limit(20).all())


@bp.post("/expire-unpaid")
@role_required("admin")
def expire_unpaid():
    from flask import current_app
    n = payment_service.expire_stale_orders(current_app.config["PAYMENT_TIMEOUT_MINUTES"])
    flash(f"{n} unpaid order(s) expired.", "info")
    return redirect(url_for("admin.reports"))


@bp.post("/sweep-no-shows")
@role_required("admin")
def sweep_no_shows():
    n = order_service.sweep_no_shows()
    flash(f"{n} overdue pickup(s) marked as no-show.", "info")
    return redirect(url_for("admin.reports"))


@bp.get("/reports-data")
@role_required("admin")
def reports_data():
    return jsonify(sales=report_service.daily_sales(), top=report_service.top_items())
