import enum

from app.extensions import db
from app.utils.timeutil import utcnow


class OrderStatus(enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PREPARING = "PREPARING"
    READY = "READY"
    COLLECTED = "COLLECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NO_SHOW = "NO_SHOW"  # ready but never picked up (slot + grace period passed)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("time_slots.id"), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING_PAYMENT)
    token = db.Column(db.String(10), unique=True)          # pickup token, set after payment
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", backref="orders")
    slot = db.relationship("TimeSlot")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    # --- business-rule helpers (no schema change) ---
    def age_minutes(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - (self.created_at or now)).total_seconds() / 60.0

    def can_cancel(self, window_minutes=5):
        """5-minute cancel window: PENDING_PAYMENT always, PAID only within window."""
        if self.status == OrderStatus.PENDING_PAYMENT:
            return True
        if self.status == OrderStatus.PAID:
            return self.age_minutes() <= window_minutes
        return False

    def is_pickup_overdue(self, grace_minutes=60):
        """True when a READY order passed its slot + grace (no-pickup case)."""
        if self.status != OrderStatus.READY or not self.slot:
            return False
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return now > (self.slot.start_time + timedelta(minutes=grace_minutes))


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(8, 2), nullable=False)

    item = db.relationship("MenuItem")
