from sqlalchemy import func

from app.extensions import db
from app.models import MenuItem, Order, OrderItem, OrderStatus

PAID_STATES = (OrderStatus.PAID, OrderStatus.PREPARING,
               OrderStatus.READY, OrderStatus.COLLECTED)


def daily_sales(limit=14):
    day = func.date(Order.created_at)
    rows = (db.session.query(day.label("day"), func.count(Order.id), func.sum(Order.total))
            .filter(Order.status.in_(PAID_STATES))
            .group_by(day).order_by(day.desc()).limit(limit).all())
    return [{"day": str(d), "orders": n, "revenue": float(r or 0)} for d, n, r in rows]


def top_items(limit=5):
    rows = (db.session.query(MenuItem.name, func.sum(OrderItem.quantity).label("qty"))
            .join(OrderItem, OrderItem.item_id == MenuItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.status.in_(PAID_STATES))
            .group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit).all())
    return [{"name": n, "qty": int(q)} for n, q in rows]
