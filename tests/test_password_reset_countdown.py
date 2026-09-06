import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from platform_app import create_app, db
from platform_app.config import Config
from platform_app.models import User, Event, Guest, Invitation
from platform_app.services.password_reset import create_reset_token, get_reset_user, send_reset_email
from werkzeug.security import generate_password_hash, check_password_hash


class FeatureTests(unittest.TestCase):
    def setUp(self):
        with patch.object(Config, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:'):
            self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY='test-only-secret')
        self.context = self.app.app_context()
        self.context.push()
        self.user = User(email='client@example.com', password_hash=generate_password_hash('old-password'), role='client')
        db.session.add(self.user)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def token(self):
        return create_reset_token(self.user)

    def test_reset_and_login_and_single_use(self):
        token = self.token()
        path = '/auth/reset-password/' + token
        self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post(path, data={'password': 'new-password', 'password_confirm': 'new-password'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.post(path, data={'password': 'another-password', 'password_confirm': 'another-password'}).status_code, 400)
        old = self.client.post('/auth/login', data={'email': self.user.email, 'password': 'old-password'})
        self.assertTrue(old.location.endswith('/auth/login'))
        new = self.client.post('/auth/login', data={'email': self.user.email, 'password': 'new-password'})
        self.assertTrue(new.location.endswith('/client/dashboard'))

    def test_expired_tampered_and_disabled(self):
        with patch('itsdangerous.timed.time.time', return_value=1000):
            expired = self.token()
        self.assertIsNone(get_reset_user(expired))
        self.assertIsNone(get_reset_user(self.token() + 'tampered'))
        token = self.token()
        self.user.is_active = False
        db.session.commit()
        self.assertIsNone(get_reset_user(token))

    def test_password_validation_does_not_consume_link(self):
        token = self.token()
        path = '/auth/reset-password/' + token
        for password, confirmation in [('short', 'short'), ('new-password', 'different'), ('x'*257, 'x'*257)]:
            self.assertEqual(self.client.post(path, data={'password': password, 'password_confirm': confirmation}).status_code, 200)
            self.assertIsNotNone(get_reset_user(token))
        self.assertTrue(check_password_hash(self.user.password_hash, 'old-password'))

    def test_generic_request_and_mail_failure(self):
        with patch('platform_app.routes.auth.send_reset_email') as send:
            known = self.client.post('/auth/forgot-password', data={'email': ' CLIENT@example.com '}, follow_redirects=True)
            send.assert_called_once()
            unknown = self.client.post('/auth/forgot-password', data={'email': 'unknown@example.com'}, follow_redirects=True)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(known.data, unknown.data)
            send.side_effect = RuntimeError('SMTP unavailable')
            self.assertEqual(self.client.post('/auth/forgot-password', data={'email': self.user.email}).status_code, 302)

    def test_inactive_account_gets_no_email(self):
        self.user.is_active = False
        db.session.commit()
        with patch('platform_app.routes.auth.send_reset_email') as send:
            self.client.post('/auth/forgot-password', data={'email': self.user.email})
            send.assert_not_called()

    def test_email_transport_and_trusted_link(self):
        self.app.config.update(MAIL_HOST='smtp.example.com', MAIL_FROM='sender@example.com', MAIL_USERNAME='sender', MAIL_PASSWORD='test-password', BASE_PUBLIC_URL='https://invitations.example.com')
        with self.app.test_request_context('/auth/forgot-password', base_url='https://untrusted.example.com'):
            with patch('platform_app.services.password_reset.smtplib.SMTP') as smtp:
                send_reset_email(self.user)
                connection = smtp.return_value.__enter__.return_value
                connection.starttls.assert_called_once()
                connection.login.assert_called_once_with('sender', 'test-password')
                message = connection.send_message.call_args.args[0]
                self.assertIn('https://invitations.example.com/auth/reset-password/', message.get_content())
                self.assertNotIn('untrusted.example.com', message.get_content())
                self.assertEqual(message['To'], self.user.email)

    def test_csrf_and_private_headers(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        self.assertEqual(self.client.post('/auth/forgot-password', data={'email': self.user.email}).status_code, 400)
        path = '/auth/reset-password/' + self.token()
        self.assertEqual(self.client.post(path, data={'password': 'new-password'}).status_code, 400)
        response = self.client.get(path)
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_countdown_and_existing_event_invitation_flows(self):
        self.client.post('/auth/login', data={'email': self.user.email, 'password': 'old-password'})
        event_data = {'title': 'Test event', 'event_datetime': '2027-12-20T16:00', 'location_name': 'Salle', 'address': 'Adresse', 'is_active': 'on'}
        self.assertEqual(self.client.post('/client/events', data=event_data).status_code, 302)
        event = Event.query.one()
        dashboard = self.client.get('/client/dashboard')
        self.assertIn(b'data-event-countdown="2027-12-20T16:00:00"', dashboard.data)
        self.assertEqual(self.client.get(f'/client/events/{event.id}/guests').status_code, 200)
        self.assertEqual(self.client.get(f'/client/events/{event.id}/invitations').status_code, 200)
        event_data['event_datetime'] = '2028-01-01T18:30'
        self.client.post(f'/client/events/{event.id}/edit', data=event_data)
        self.assertIn(b'2028-01-01T18:30:00', self.client.get(f'/client/events/{event.id}/edit').data)
        guest = Guest(event_id=event.id, full_name='Guest', guest_type='single', party_size=1)
        db.session.add(guest)
        db.session.flush()
        invitation = Invitation(event_id=event.id, guest_id=guest.id, invitation_code='test-code')
        db.session.add(invitation)
        db.session.commit()
        public = self.app.test_client()
        self.assertEqual(public.get('/i/test-code').status_code, 200)
        self.assertEqual(public.post('/i/test-code/rsvp', data={'status': 'yes'}, follow_redirects=True).status_code, 200)
        self.assertEqual(invitation.rsvp.status, 'yes')
        event.is_active = False
        db.session.commit()
        self.assertNotIn(b'data-event-countdown=', self.client.get('/client/dashboard').data)

    def test_other_client_cannot_access_event(self):
        other = User(email='other@example.com', password_hash=generate_password_hash('other-password'), role='client')
        db.session.add(other)
        db.session.flush()
        event = Event(user_id=other.id, title='Private', event_datetime=datetime(2027, 1, 1), location_name='Room', address='Address')
        db.session.add(event)
        db.session.commit()
        self.client.post('/auth/login', data={'email': self.user.email, 'password': 'old-password'})
        self.assertEqual(self.client.get(f'/client/events/{event.id}/edit').status_code, 403)
        self.assertNotIn(b'Private', self.client.get('/client/dashboard').data)


if __name__ == '__main__':
    unittest.main()
