"""Application factory."""
import logging
import time

from flask import Flask, jsonify, render_template

from config import Config


def _resolve_db_uri(app):
    """Use MySQL when reachable, else fall back to a local SQLite file.

    This fixes 'no real database connectivity': production uses MySQL
    (DATABASE_URL), but developers without MySQL still get a working app
    instead of a crash on startup. /health/db always reports which one.
    """
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not app.config.get("DB_FALLBACK_SQLITE", True) or not uri.startswith("mysql"):
        return uri
    try:
        import pymysql

        # Parse mysql+pymysql://user:pw@host:port/db
        from sqlalchemy.engine.url import make_url

        url = make_url(uri)
        conn = pymysql.connect(host=url.host or "localhost", port=url.port or 3306,
                               user=url.username, password=url.password,
                               database=url.database, connect_timeout=2)
        conn.close()
        return uri
    except Exception as exc:  # noqa: BLE001 - fallback is intentional
        logging.getLogger(__name__).warning("MySQL unreachable (%s); using SQLite fallback.", exc)
        import os

        os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
        return "sqlite:///" + os.path.abspath(
            os.path.join(app.root_path, "..", "instance", "canteen.db")
        )


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from .extensions import csrf, db, login_manager

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    # Strong session protection: mismatched IP/user-agent invalidates the session.
    login_manager.session_protection = "strong"

    # Resolve DB (MySQL preferred, SQLite fallback) before first use.
    app.config["SQLALCHEMY_DATABASE_URI"] = _resolve_db_uri(app)
    _uri = app.config["SQLALCHEMY_DATABASE_URI"]
    app.config["DB_BACKEND"] = (
        "mysql" if _uri.startswith("mysql")
        else "postgres" if "postgres" in _uri.split("://")[0]
        else "sqlite"
    )

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import admin, auth, menu, orders, payments, staff

    for module in (auth, menu, orders, payments, staff, admin):
        app.register_blueprint(module.bp)

    @app.get("/health/db")
    def db_health():
        """Real database connectivity probe (used by docker/k8s and the admin dashboard)."""
        from sqlalchemy import text

        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(ok=True, backend=app.config.get("DB_BACKEND", "unknown"))
        except Exception as exc:  # noqa: BLE001
            return jsonify(ok=False, error=str(exc)[:200]), 500

    @app.before_request
    def auto_housekeeping():
        """Automatically expire unpaid orders and sweep no-shows (throttled).

        Unpaid orders older than PAYMENT_TIMEOUT_MINUTES are failed and their
        slots freed; READY orders past slot+PICKUP_GRACE_MINUTES become NO_SHOW.
        Runs at most once every 45s so normal requests stay cheap.
        """
        now = time.monotonic()
        if now - getattr(app, "_last_sweep", 0) < 45:
            return
        app._last_sweep = now
        try:
            from app.services import order_service, payment_service

            payment_service.expire_stale_orders(
                app.config.get("PAYMENT_TIMEOUT_MINUTES", 10))
            order_service.sweep_no_shows()
            order_service.rollover_slots()  # keep daily slots date-agnostic
        except Exception:  # noqa: BLE001 - housekeeping must never break requests
            db.session.rollback()

    @app.context_processor
    def inject_csrf():
        from flask_wtf.csrf import generate_csrf
        from markupsafe import Markup

        def csrf():
            return Markup(f'<input type="hidden" name="csrf_token" value="{generate_csrf()}">')
        return {"csrf": csrf}

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="Access denied."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="Page not found."), 404

    with app.app_context():
        db.create_all()

    return app
