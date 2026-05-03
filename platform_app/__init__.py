import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# ✅ IMPORTANT: ton endpoint login s'appelle auth.login_get
login_manager.login_view = "auth.login_get"


def create_app():
    app = Flask(__name__)

    # --- CONFIG ---
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # DB
    db_uri = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Storage
    storage_dir = os.environ.get("STORAGE_DIR", os.path.join(os.getcwd(), "storage"))
    app.config["STORAGE_DIR"] = storage_dir

    # URL publique (QR)
    app.config["BASE_PUBLIC_URL"] = os.environ.get("BASE_PUBLIC_URL", "http://127.0.0.1:5000")

    # --- INIT EXTENSIONS ---
    db.init_app(app)
    login_manager.init_app(app)

    # --- USER LOADER ---
    from .models import User  # éviter circular import

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # --- BLUEPRINTS ---
    from .routes.auth import bp as auth_bp
    from .routes.client import bp as client_bp
    from .routes.public import bp as public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(public_bp)

    # Home simple
    @app.get("/")
    def home():
        return (
            "<h3>OK - Plateforme Invitations</h3>"
            "<p><a href='/auth/login'>Login</a> | <a href='/auth/register'>Register</a></p>"
        )

    return app
