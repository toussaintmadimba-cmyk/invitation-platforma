"""Compatibility entry point; schema changes are managed by Alembic."""

from flask_migrate import upgrade

from platform_app import create_app


app = create_app()

with app.app_context():
    upgrade()
    print("Migration Alembic appliquee.")
