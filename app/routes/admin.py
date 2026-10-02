from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import MenuItem, TimeSlot
from app.services import payment_service, report_service
from app.utils.decorators import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/menu", methods=["GET", "POST"])
@role_required("admin", "staff")
def menu():
    if request.method == "POST":
        try:
            price = Decimal(request.form.get("price", "0"))
            stock = int(request.form.get("stock", "0"))
            name = request.form.get("name", "").strip()
            if not name or price <= 0 or stock < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a name, a positive price and a valid stock.", "danger")
        else:
            db.session.add(MenuItem(name=name, price=price, stock=stock,
                                    category=request.form.get("category", "Snacks").strip() or "Snacks"))
            db.session.commit()
            flash("Menu item added.", "success")
        return redirect(url_for("admin.menu"))
    return render_template("admin/menu.html", items=MenuItem.query.order_by(MenuItem.category, MenuItem.name).all())


@bp.post("/menu/<int:item_id>/update")
@role_required("admin", "staff")
def update_item(item_id):
    item = db.session.get(MenuItem, item_id)
    if item:
        item.stock = max(0, request.form.get("stock", item.stock, type=int))
        item.is_available = request.form.get("is_available") == "on"
        db.session.commit()
    return redirect(url_for("admin.menu"))


@bp.route("/slots", methods=["GET", "POST"])
@role_required("admin")
def slots():
    if request.method == "POST":
        try:
            start = datetime.strptime(request.form["start_time"], "%Y-%m-%dT%H:%M")
            capacity = int(request.form["capacity"])
            if capacity < 1:
                raise ValueError
        except (KeyError, ValueError):
            flash("Enter a valid start time and capacity.", "danger")
        else:
            db.session.add(TimeSlot(start_time=start, capacity=capacity))
            db.session.commit()
            flash("Time slot created.", "success")
        return redirect(url_for("admin.slots"))
    return render_template("admin/slots.html", slots=TimeSlot.query.order_by(TimeSlot.start_time.desc()).limit(30).all())


@bp.get("/reports")
@role_required("admin")
def reports():
    return render_template("admin/reports.html",
                           sales=report_service.daily_sales(),
                           top=report_service.top_items())


@bp.post("/expire-unpaid")
@role_required("admin")
def expire_unpaid():
    from flask import current_app
    n = payment_service.expire_stale_orders(current_app.config["PAYMENT_TIMEOUT_MINUTES"])
    flash(f"{n} unpaid order(s) expired.", "info")
    return redirect(url_for("admin.reports"))
