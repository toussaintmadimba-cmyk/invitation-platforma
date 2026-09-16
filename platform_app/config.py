import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SQLITE_DB_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "instance", "app.db")
)
DEFAULT_SQLITE_DATABASE_URL = "sqlite:///" + DEFAULT_SQLITE_DB_PATH.replace("\\", "/")


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://"):]
    return database_url


class Config:
    APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))
    MAIL_HOST = os.environ.get("MAIL_HOST", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    PASSWORD_RESET_MAX_AGE = 1800
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("DATABASE_URL", DEFAULT_SQLITE_DATABASE_URL)
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STORAGE_DIR = os.environ.get(
        "STORAGE_DIR",
        os.path.join(BASE_DIR, "storage")
    )

    BASE_PUBLIC_URL = os.environ.get(
        "BASE_PUBLIC_URL",
        "http://127.0.0.1:5000"
    )


def validate_production_config(config):
    if config.get("APP_ENV") != "production":
        return
    from urllib.parse import urlparse
    if config.get("SECRET_KEY") in {None, "", "dev-secret-key-change-me", "change-moi-en-production"}:
        raise RuntimeError("SECRET_KEY privée obligatoire en production.")
    if config.get("SQLALCHEMY_DATABASE_URI") == DEFAULT_SQLITE_DATABASE_URL:
        raise RuntimeError("DATABASE_URL explicite obligatoire en production.")
    url = urlparse(config.get("BASE_PUBLIC_URL", ""))
    if url.scheme != "https" or not url.netloc or url.path not in {"", "/"}:
        raise RuntimeError("BASE_PUBLIC_URL doit être une origine HTTPS en production.")
