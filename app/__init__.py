"""Application factory."""
from flask import Flask, render_template

from config import Config

from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import admin, auth, menu, orders, payments, staff

    for module in (auth, menu, orders, payments, staff, admin):
        app.register_blueprint(module.bp)

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
