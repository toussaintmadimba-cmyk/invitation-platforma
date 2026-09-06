"""Signed, expiring reset links invalidated by any password change."""
import hashlib
import hmac
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .. import db
from ..models import User


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset-v1")


def _fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()


def create_reset_token(user):
    return _serializer().dumps({"uid": user.id, "password": _fingerprint(user)})


def get_reset_user(token):
    try:
        data = _serializer().loads(token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE"])
        if not isinstance(data, dict):
            return None
        user = db.session.get(User, data.get("uid"))
        fingerprint = data.get("password")
        if user and user.is_active and isinstance(fingerprint, str):
            if hmac.compare_digest(fingerprint, _fingerprint(user)):
                return user
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        pass
    return None


def send_reset_email(user):
    config = current_app.config
    if not config["MAIL_HOST"] or not config["MAIL_FROM"]:
        raise RuntimeError("Email configuration missing")
    token = create_reset_token(user)
    link = config["BASE_PUBLIC_URL"].rstrip("/") + url_for("auth.reset_password", token=token)
    message = EmailMessage()
    message["Subject"] = "Réinitialiser votre mot de passe — Invitations"
    message["From"] = config["MAIL_FROM"]
    message["To"] = user.email
    minutes = config["PASSWORD_RESET_MAX_AGE"] // 60
    message.set_content(
        f"Pour choisir un nouveau mot de passe, ouvrez ce lien :\n\n{link}\n\n"
        f"Ce lien est valable {minutes} minutes et ne peut être utilisé qu'une fois.\n"
        "Si vous n'avez pas demandé ce changement, ignorez cet email."
    )
    context = ssl.create_default_context()
    transport = smtplib.SMTP_SSL if config["MAIL_USE_SSL"] else smtplib.SMTP
    options = {"timeout": 15}
    if config["MAIL_USE_SSL"]:
        options["context"] = context
    with transport(config["MAIL_HOST"], config["MAIL_PORT"], **options) as smtp:
        if config["MAIL_USE_TLS"] and not config["MAIL_USE_SSL"]:
            smtp.starttls(context=context)
        if config["MAIL_USERNAME"]:
            smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
        smtp.send_message(message)
