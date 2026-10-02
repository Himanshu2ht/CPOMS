import enum

from app.extensions import db
from app.utils.timeutil import utcnow


class PaymentStatus(enum.Enum):
    CREATED = "CREATED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, unique=True)
    gateway_ref = db.Column(db.String(40), unique=True, nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.CREATED)
    created_at = db.Column(db.DateTime, default=utcnow)
    paid_at = db.Column(db.DateTime)

    order = db.relationship("Order", backref=db.backref("payment", uselist=False))
