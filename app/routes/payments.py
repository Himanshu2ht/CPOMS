import json

from flask import (Blueprint, abort, current_app, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from app import gateway
from app.extensions import csrf
from app.models import Payment
from app.services import payment_service

bp = Blueprint("payments", __name__, url_prefix="/payments")


def _own_payment(ref):
    payment = Payment.query.filter_by(gateway_ref=ref).first() or abort(404)
    if payment.order.user_id != current_user.id:
        abort(404)
    return payment


@bp.get("/checkout/<ref>")
@login_required
def checkout(ref):
    """Sandbox checkout page standing in for the gateway's hosted page."""
    return render_template("payments/checkout.html", payment=_own_payment(ref))


@bp.post("/checkout/<ref>/complete")
@login_required
def complete(ref):
    payment = _own_payment(ref)
    success = request.form.get("outcome") == "success"
    payment_service.handle_event(payment.gateway_ref, success)
    return redirect(url_for("orders.detail", order_id=payment.order_id))


@bp.post("/webhook")
@csrf.exempt                      # called server-to-server; authenticated by HMAC
def webhook():
    body = request.get_data()
    signature = request.headers.get("X-Signature", "")
    if not gateway.verify_signature(body, signature, current_app.config["PAYMENT_WEBHOOK_SECRET"]):
        return jsonify(error="invalid signature"), 400
    data = json.loads(body or b"{}")
    result = payment_service.handle_event(data.get("ref"), data.get("status") == "success")
    return jsonify(result), (200 if result["success"] else 404)
