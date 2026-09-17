from platform_app import create_app
from flask_migrate import upgrade

app = create_app()

with app.app_context():
    upgrade()
    print("DB initialisee/mise a jour par Alembic.")
