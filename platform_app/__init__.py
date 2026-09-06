from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# ✅ IMPORTANT: ton endpoint login s'appelle auth.login_get
login_manager.login_view = "auth.login_get"


def _user_is_active_column_exists():
    columns = inspect(db.engine).get_columns("user")
    return any(column["name"] == "is_active" for column in columns)


def _ensure_user_is_active_column():
    if _user_is_active_column_exists():
        return

    active_value = "TRUE" if db.engine.dialect.name == "postgresql" else "1"
    try:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    f'ALTER TABLE "user" ADD COLUMN is_active '
                    f'BOOLEAN NOT NULL DEFAULT {active_value}'
                )
            )
    except SQLAlchemyError:
        if not _user_is_active_column_exists():
            raise

    with db.engine.begin() as connection:
        connection.execute(
            text(
                f'UPDATE "user" SET is_active = {active_value} '
                'WHERE is_active IS NULL'
            )
        )


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- INIT EXTENSIONS ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- USER LOADER ---
    from .models import User  # éviter circular import

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            user = db.session.get(User, int(user_id))
            if user is None or not user.is_active:
                return None
            return user
        except Exception:
            db.session.rollback()
            app.logger.exception("Erreur lors du chargement de l'utilisateur")
            return None

    # --- BLUEPRINTS ---
    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.client import bp as client_bp
    from .routes.public import bp as public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(public_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        app.logger.warning("Requête CSRF refusée : %s", error.description)
        return render_template(
            "errors/csrf_error.html",
            reason=error.description,
        ), 400

    # --- CREATION DES TABLES ---
    with app.app_context():
        db.create_all()
        _ensure_user_is_active_column()

    return app
