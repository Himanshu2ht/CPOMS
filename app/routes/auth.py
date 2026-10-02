from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User
from app.utils.security import (clear_attempts, is_rate_limited, password_errors,
                                record_attempt)

bp = Blueprint("auth", __name__)


def _safe_next(target):
    """Only allow same-site relative redirects (prevents open redirect)."""
    return target if target and target.startswith("/") and not target.startswith("//") else None


def _client_key():
    return f"{request.remote_addr}:{request.form.get('email', '').strip().lower()}"


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        policy = password_errors(password)
        if not name or "@" not in email:
            flash("Enter a name and a valid email.", "danger")
        elif policy:
            flash("Password must be 8+ characters with " + ", ".join(policy) + ".", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            user = User(name=name, email=email, role="customer")
            user.set_password(password)  # werkzeug scrypt hash, never stored plain
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        key = _client_key()
        max_n = current_app.config.get("LOGIN_RATELIMIT_ATTEMPTS", 5)
        window = current_app.config.get("LOGIN_RATELIMIT_WINDOW_SECONDS", 300)
        if is_rate_limited(key, max_n, window):
            flash("Too many failed attempts. Try again in a few minutes.", "danger")
        else:
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(request.form.get("password", "")):
                clear_attempts(key)
                login_user(user)  # Flask-Login signed session cookie (HttpOnly, SameSite=Lax)
                return redirect(_safe_next(request.args.get("next")) or url_for("menu.index"))
            record_attempt(key)
            flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile: how authentication state is visible/editable.

    Shows name, email, role (role itself is admin-assigned, never self-editable)
    and lets the user change name + password.
    """
    if request.method == "POST":
        action = request.form.get("action", "update")
        if action == "update":
            name = request.form.get("name", "").strip()
            if name:
                current_user.name = name
                db.session.commit()
                flash("Profile updated.", "success")
            else:
                flash("Name cannot be empty.", "danger")
        elif action == "password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "danger")
            else:
                policy = password_errors(new_pw)
                if policy:
                    flash("New password needs " + ", ".join(policy) + ".", "danger")
                else:
                    current_user.set_password(new_pw)
                    db.session.commit()
                    flash("Password changed.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
