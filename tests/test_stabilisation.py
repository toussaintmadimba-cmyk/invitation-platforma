import re
from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import test_password_reset_countdown as features
from platform_app import db
from platform_app.models import Event, Guest, Invitation, RSVP
from platform_app.services.invitation_generator import generate_all_invitations_for_event
from platform_app.services.cloud_storage import UploadedInvitationFiles, upload_invitation_files
from platform_app.services.password_reset import send_email, validate_mail_config
from platform_app.config import validate_production_config
from maintenance import migrate, sqlite_copy, verify_backup, backup


class StabilisationTests(unittest.TestCase):
    setUp = features.FeatureTests.setUp
    tearDown = features.FeatureTests.tearDown

    def event(self):
        event = Event(user_id=self.user.id, title="Test", event_datetime=datetime(2027, 1, 1), location_name="Salle", address="Adresse")
        db.session.add(event)
        db.session.commit()
        return event

    def guest(self, event, name="Invité", size=1):
        guest = Guest(event_id=event.id, full_name=name, guest_type="single" if size == 1 else "family", party_size=size)
        db.session.add(guest)
        db.session.commit()
        return guest

    def invitation(self, event):
        guest = self.guest(event)
        invitation = Invitation(event_id=event.id, guest_id=guest.id, invitation_code="test-stable-code")
        db.session.add(invitation)
        db.session.commit()
        return invitation

    def test_get_rsvp_never_writes_post_requires_csrf(self):
        self.invitation(self.event())
        self.app.config["WTF_CSRF_ENABLED"] = True
        path = "/i/test-stable-code/rsvp"
        response = self.client.get(path + "?status=yes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RSVP.query.count(), 0)
        self.assertEqual(self.client.post(path, data={"status": "yes"}).status_code, 400)
        token = re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()
        self.assertEqual(self.client.post(path, data={"status": "yes", "csrf_token": token}).status_code, 302)
        self.client.get(path + "?status=no")
        self.assertEqual(RSVP.query.one().status, "yes")
        self.client.get(path + "?status=later")
        self.assertEqual(RSVP.query.one().status, "yes")

    def test_inactive_event_or_owner_blocks_all_public_routes(self):
        event = self.event()
        self.invitation(event)
        for target in (event, self.user):
            target.is_active = False
            db.session.commit()
            for suffix in ("", "/rsvp?status=yes", "/merci"):
                self.assertEqual(self.client.get("/i/test-stable-code" + suffix).status_code, 404)
            self.assertEqual(self.client.post("/i/test-stable-code/rsvp", data={"status": "yes"}).status_code, 404)
            self.assertEqual(RSVP.query.count(), 0)
            target.is_active = True
            db.session.commit()

    def test_invalid_quotas_rejected_and_defaults_accepted(self):
        event = self.event()
        self.client.post("/auth/login", data={"email": self.user.email, "password": "old-password"})
        path = f"/client/events/{event.id}/guests"
        for kind, size in (("family", "-3"), ("family", "0"), ("family", "101"), ("family", "1"), ("couple", "3"), ("single", "2"), ("family", "2.5"), ("unknown", "1")):
            self.client.post(path, data={"full_name": "Test", "guest_type": kind, "party_size": size})
            self.assertEqual(Guest.query.count(), 0)
        for kind in ("single", "couple", "family"):
            self.client.post(path, data={"full_name": "Test", "guest_type": kind})
        self.assertEqual([g.party_size for g in Guest.query.order_by(Guest.id)], [1, 2, 3])
        page = self.client.get("/client/dashboard").data.decode()
        self.assertIn('>6</div>', page)
        self.assertIn('3 groupe(s)', page)
        self.assertNotIn('Invités confirmés', page)

    def test_database_constraints_protect_direct_writes(self):
        event = self.event()
        with self.assertRaises(IntegrityError):
            db.session.add(Guest(event_id=event.id, full_name="Bad", guest_type="family", party_size=-1))
            db.session.commit()
        db.session.rollback()
        inv = self.invitation(event)
        with self.assertRaises(IntegrityError):
            db.session.add(Invitation(event_id=event.id, guest_id=inv.guest_id, invitation_code="another"))
            db.session.commit()
        db.session.rollback()

    def test_generation_failure_preserves_success_and_retry_preserves_code(self):
        event = self.event()
        self.guest(event)
        self.guest(event, "Second")
        with tempfile.TemporaryDirectory() as folder, patch("platform_app.services.invitation_generator.TemplateRenderer"), patch("platform_app.services.invitation_generator.upload_invitation_files") as upload:
            upload.side_effect = [UploadedInvitationFiles("https://test/one.pdf", "https://test/one.png"), RuntimeError("failure")]
            result = generate_all_invitations_for_event(event=event, storage_dir=folder, base_public_url="https://test")
            self.assertEqual((result["files_generated"], result["errors"]), (1, 1))
            self.assertEqual(Invitation.query.filter(Invitation.pdf_path.isnot(None)).count(), 1)
            codes = [i.invitation_code for i in Invitation.query.order_by(Invitation.id)]
            upload.side_effect = None
            upload.return_value = UploadedInvitationFiles("https://test/two.pdf", "https://test/two.png")
            result = generate_all_invitations_for_event(event=event, storage_dir=folder, base_public_url="https://test")
            self.assertEqual((result["files_generated"], result["errors"]), (1, 0))
            self.assertEqual([i.invitation_code for i in Invitation.query.order_by(Invitation.id)], codes)
            self.assertEqual(list((Path(folder) / "tmp").iterdir()), [])

    def test_failed_regeneration_keeps_old_files(self):
        event = self.event()
        inv = self.invitation(event)
        inv.pdf_path, inv.qr_path = "https://old/pdf", "https://old/qr"
        db.session.commit()
        with tempfile.TemporaryDirectory() as folder, patch("platform_app.services.invitation_generator.TemplateRenderer"), patch("platform_app.services.invitation_generator.upload_invitation_files", side_effect=RuntimeError("failure")):
            result = generate_all_invitations_for_event(event=event, storage_dir=folder, base_public_url="https://test", force=True)
            self.assertEqual(result["files_generated"], 0)
            self.assertEqual((inv.pdf_path, inv.qr_path, inv.invitation_code), ("https://old/pdf", "https://old/qr", "test-stable-code"))

    def test_two_generators_keep_one_invitation_and_one_file_pair(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from platform_app import create_app
        from platform_app.config import Config
        from platform_app.models import User
        with tempfile.TemporaryDirectory() as folder:
            url = "sqlite:///" + str(Path(folder) / "concurrent.db").replace("\\", "/")
            with patch.object(Config, "SQLALCHEMY_DATABASE_URI", url):
                app = create_app()
            with app.app_context():
                user = User(email="concurrency@example.test", password_hash="unused")
                db.session.add(user)
                db.session.flush()
                event = Event(user_id=user.id, title="Concurrent", event_datetime=datetime(2027, 1, 1), location_name="Room", address="Address")
                db.session.add(event)
                db.session.flush()
                db.session.add(Guest(event_id=event.id, full_name="One", guest_type="single", party_size=1))
                db.session.commit()
                event_id = event.id
            barrier = Barrier(2, timeout=15)
            def upload(**kwargs):
                barrier.wait()
                return UploadedInvitationFiles("https://new/pdf", "https://new/qr")
            def generate():
                with app.app_context():
                    return generate_all_invitations_for_event(event=db.session.get(Event, event_id), storage_dir=folder, base_public_url="https://test")
            try:
                with patch("platform_app.services.invitation_generator.TemplateRenderer"), patch("platform_app.services.invitation_generator.upload_invitation_files", side_effect=upload), patch("platform_app.services.invitation_generator.delete_uploaded_invitation_files"), ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: generate(), range(2)))
                self.assertEqual(sum(r["files_generated"] for r in results), 1)
                with app.app_context():
                    self.assertEqual(Invitation.query.count(), 1)
                    self.assertEqual(Invitation.query.one().pdf_path, "https://new/pdf")
            finally:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()

    def test_failed_database_update_cleans_new_uploads(self):
        event = self.event()
        self.invitation(event)
        with tempfile.TemporaryDirectory() as folder, patch("platform_app.services.invitation_generator.TemplateRenderer"), patch("platform_app.services.invitation_generator.upload_invitation_files", return_value=UploadedInvitationFiles("pdf", "qr", "new-pdf", "new-qr")), patch("flask_sqlalchemy.query.Query.update", side_effect=RuntimeError("db failure")), patch("platform_app.services.invitation_generator.delete_uploaded_invitation_files") as cleanup:
            result = generate_all_invitations_for_event(event=event, storage_dir=folder, base_public_url="https://test")
            self.assertEqual(result["errors"], 1)
            self.assertEqual(result["files_generated"], 0)
            self.assertIsNone(Invitation.query.one().pdf_path)
            cleanup.assert_called_once()

    def test_real_renderer_produces_pdf_and_qr_before_upload(self):
        event = self.event()
        self.guest(event)
        import shutil
        def upload(**kwargs):
            self.assertTrue(Path(kwargs["pdf_path"]).read_bytes().startswith(b"%PDF"))
            self.assertTrue(Path(kwargs["qr_path"]).read_bytes().startswith(b"\x89PNG"))
            return UploadedInvitationFiles("https://test/pdf", "https://test/qr")
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(Path(__file__).resolve().parents[1] / "storage/templates", Path(folder) / "templates")
            with patch("platform_app.services.invitation_generator.upload_invitation_files", side_effect=upload):
                result = generate_all_invitations_for_event(event=event, storage_dir=folder, base_public_url="https://test")
            self.assertEqual(result["files_generated"], 1)

    def test_second_cloud_upload_failure_only_deletes_new_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf, qr = Path(folder) / "a.pdf", Path(folder) / "a.png"
            pdf.write_bytes(b"pdf")
            qr.write_bytes(b"png")
            with patch("platform_app.services.cloud_storage._validate_cloudinary_config"), patch("cloudinary.uploader.upload") as upload, patch("cloudinary.uploader.destroy") as destroy:
                upload.side_effect = [{"public_id": "new-revision", "secure_url": "https://test/new"}, RuntimeError("second failed")]
                with self.assertRaises(RuntimeError):
                    upload_invitation_files(pdf_path=str(pdf), qr_path=str(qr), event_id=1, guest_id=1)
                destroy.assert_called_once_with("new-revision", resource_type="raw", invalidate=True)
                self.assertFalse(upload.call_args_list[0].kwargs["overwrite"])
                self.assertNotEqual(upload.call_args_list[0].kwargs["public_id"], "invitation-platforma/events/event_1/pdf/invite_1.pdf")

    def test_ssl_transport_and_invalid_configuration(self):
        from email.message import EmailMessage
        config = dict(self.app.config, MAIL_HOST="smtp.test", MAIL_FROM="test@example.com", MAIL_USERNAME="user", MAIL_PASSWORD="test", MAIL_USE_SSL=True, MAIL_USE_TLS=False)
        with patch("platform_app.services.password_reset.smtplib.SMTP_SSL") as smtp:
            send_email(EmailMessage(), config)
            connection = smtp.return_value.__enter__.return_value
            connection.starttls.assert_not_called()
            connection.login.assert_called_once_with("user", "test")
            connection.send_message.assert_called_once()
        config["MAIL_USE_TLS"] = True
        with self.assertRaises(RuntimeError):
            validate_mail_config(config)

    def test_production_rejects_development_settings(self):
        config = dict(self.app.config, APP_ENV="production", SECRET_KEY="dev-secret-key-change-me")
        with self.assertRaises(RuntimeError):
            validate_production_config(config)


class MaintenanceTests(unittest.TestCase):
    def legacy_engine(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as c:
            c.execute(text("CREATE TABLE guest (id INTEGER PRIMARY KEY, guest_type TEXT, party_size INTEGER, partner_name TEXT)"))
            c.execute(text("CREATE TABLE invitation (id INTEGER PRIMARY KEY, guest_id INTEGER)"))
            c.execute(text("INSERT INTO guest VALUES (1, 'couple', 2, 'Legacy')"))
            c.execute(text("INSERT INTO invitation VALUES (1, 1)"))
        self.addCleanup(engine.dispose)
        return engine

    def test_migration_preserves_legacy_columns_and_enforces_rules(self):
        engine = self.legacy_engine()
        self.assertEqual(migrate(engine), {"invalid_groups": 0, "duplicate_invitations": 0})
        migrate(engine, True)
        migrate(engine, True)
        with engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT partner_name FROM guest")).scalar(), "Legacy")
        for sql in ("UPDATE guest SET party_size = -3", "INSERT INTO guest VALUES (2, 'single', 2, NULL)", "INSERT INTO invitation VALUES (2, 1)"):
            with self.assertRaises(IntegrityError), engine.begin() as c:
                c.execute(text(sql))

    def test_migration_refuses_invalid_existing_rows(self):
        engine = self.legacy_engine()
        with engine.begin() as c:
            c.execute(text("UPDATE guest SET party_size=-3"))
        self.assertEqual(migrate(engine)["invalid_groups"], 1)
        with self.assertRaises(ValueError):
            migrate(engine, True)

    def test_backup_restore_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "instance/app.db"
            source.parent.mkdir()
            with closing(sqlite3.connect(source)) as c:
                c.execute("CREATE TABLE sample (value TEXT)")
                c.execute("INSERT INTO sample VALUES ('preserved')")
                c.commit()
            with patch("maintenance.ROOT", root), patch("maintenance.DEFAULT_SQLITE_DB_PATH", str(source)):
                saved = backup()
            self.assertEqual(verify_backup(saved), 1)
            restored = root / "restored.db"
            sqlite_copy(saved / "instance/app.db", restored)
            with closing(sqlite3.connect(restored)) as c:
                self.assertEqual(c.execute("SELECT value FROM sample").fetchone()[0], "preserved")
            (saved / "instance/app.db").write_bytes(b"damaged")
            with self.assertRaises(ValueError):
                verify_backup(saved)
