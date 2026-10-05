"""Central configuration. Secrets come from environment variables (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _database_uri():
    uri = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://canteen_user:password@localhost:3306/canteen_db",
    )
    # Render/Supabase give "postgres://..." but SQLAlchemy needs the driver prefix.
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
    elif uri.startswith("postgresql://") and "+" not in uri.split("://")[0]:
        uri = uri.replace("postgresql://", "postgresql+psycopg2://", 1)
    # Supabase pooler URIs carry "?pgbouncer=true" which psycopg2 rejects as an
    # invalid DSN option — drop it (a literal ? in a password is %-encoded, so
    # a raw ? always starts the query string).
    if uri.startswith("postgresql+psycopg2://") and "?" in uri:
        uri = uri.split("?", 1)[0]
    return uri


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    # Fallback so `python run.py` still works when MySQL is down (dev convenience).
    # Set DB_FALLBACK_SQLITE=0 to fail loudly instead.
    DB_FALLBACK_SQLITE = os.getenv("DB_FALLBACK_SQLITE", "1") == "1"
    # Fresh hosted DBs start empty: auto-create demo users/menu/slots on boot
    # (only when the users table is empty; never deletes). Set AUTO_SEED=0 to
    # disable and seed manually with `python seed.py`.
    AUTO_SEED = os.getenv("AUTO_SEED", "1") == "1"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"  # set 1 behind HTTPS
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 0  # no persistent "remember me" session
    PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "whsec_dev")
    PAYMENT_TIMEOUT_MINUTES = 10          # unpaid orders expire after this
    # --- business rules (all mkdocs-visible, all tunable via env) ---
    PREP_TIME_MINUTES = int(os.getenv("PREP_TIME_MINUTES", "25"))      # kitchen needs 25 min
    CANCEL_WINDOW_MINUTES = int(os.getenv("CANCEL_WINDOW_MINUTES", "5"))  # cancel/refund within 5 min
    PICKUP_GRACE_MINUTES = int(os.getenv("PICKUP_GRACE_MINUTES", "15"))  # READY -> NO_SHOW after slot+15min
    LOGIN_RATELIMIT_ATTEMPTS = int(os.getenv("LOGIN_RATELIMIT_ATTEMPTS", "5"))
    LOGIN_RATELIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATELIMIT_WINDOW_SECONDS", "300"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    PAYMENT_WEBHOOK_SECRET = "whsec_test"
