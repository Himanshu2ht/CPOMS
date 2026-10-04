from flask import Blueprint, render_template

from app.models import MenuItem

bp = Blueprint("menu", __name__)


@bp.route("/")
def index():
    items = (MenuItem.query.filter_by(is_available=True)
             .order_by(MenuItem.category, MenuItem.name).all())
    grouped = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    return render_template("menu/index.html", grouped=grouped)
