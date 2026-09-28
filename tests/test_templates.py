import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask_migrate import upgrade
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from platform_app import create_app, db
from platform_app.config import Config
from platform_app.models import Event, Template, User


class TemplateTests(unittest.TestCase):
    def setUp(self):
        with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.default_template = Template(
            slug="template_001",
            name="Wedding Premium 4 pages",
            preview_image="templates/template_001/page_1.png",
            primary_color="#1f2937",
            secondary_color="#f8f5f0",
            accent_color="#c9a227",
            heading_font="Playfair Display",
            body_font="Inter",
            is_active=True,
        )
        self.inactive_template = Template(
            slug="inactive-test",
            name="Inactive test template",
            preview_image=None,
            primary_color="#000000",
            secondary_color="#ffffff",
            accent_color="#999999",
            heading_font="serif",
            body_font="sans-serif",
            is_active=False,
        )
        self.user = User(
            name="Template Test",
            email="template@example.test",
            password_hash=generate_password_hash("test-password"),
            role="client",
        )
        db.session.add_all(
            [self.default_template, self.inactive_template, self.user]
        )
        db.session.commit()
        self.client = self.app.test_client()
        self.client.post(
            "/auth/login",
            data={"email": self.user.email, "password": "test-password"},
        )

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    @staticmethod
    def event_data(**overrides):
        data = {
            "title": "Mariage test",
            "event_datetime": "2027-06-12T15:00",
            "location_name": "Salle test",
            "address": "1 rue du Test",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_creation_uses_default_template_and_relationship(self):
        response = self.client.post("/client/events", data=self.event_data())
        self.assertEqual(response.status_code, 302)
        event = Event.query.one()
        self.assertEqual(event.template_id, self.default_template.id)
        self.assertEqual(event.template.slug, "template_001")

    def test_unknown_or_inactive_template_is_rejected(self):
        for template_id in ("not-an-id", "999999", str(self.inactive_template.id)):
            response = self.client.post(
                "/client/events",
                data=self.event_data(template_id=template_id),
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"template actif valide", response.data)
            self.assertEqual(Event.query.count(), 0)


class TemplateMigrationTests(unittest.TestCase):
    def test_migration_seeds_once_and_backfills_existing_event(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "migration.db"
            database_url = "sqlite:///" + str(database_path).replace("\\", "/")
            with patch.object(Config, "SQLALCHEMY_DATABASE_URI", database_url):
                app = create_app()
            app.config.update(TESTING=True)
            with app.app_context():
                upgrade(revision="ccd57f95199b")
                db.session.execute(text(
                    'INSERT INTO "user" '
                    '(name, email, password_hash, role, is_active) '
                    "VALUES ('Migration', 'migration@example.test', 'unused', 'client', 1)"
                ))
                db.session.execute(text(
                    "INSERT INTO event "
                    "(user_id, title, event_datetime, location_name, address) "
                    "VALUES (1, 'Existant', :date, 'Salle', 'Adresse')"
                ), {"date": datetime(2027, 1, 1)})
                db.session.commit()

                upgrade()
                upgrade()

                template = Template.query.filter_by(slug="template_001").one()
                event = Event.query.filter_by(title="Existant").one()
                self.assertEqual(Template.query.count(), 1)
                self.assertEqual(event.template_id, template.id)
                columns = {
                    column["name"]: column
                    for column in inspect(db.engine).get_columns("event")
                }
                self.assertFalse(columns["template_id"]["nullable"])
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
