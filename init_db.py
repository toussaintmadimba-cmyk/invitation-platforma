from platform_app import create_app
from platform_app import db

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ DB initialisée: tables créées.")
