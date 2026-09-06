from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from .. import db
from ..models import User
from ..services.password_reset import get_reset_user, send_reset_email

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email, is_active=True).first()
        if user:
            try:
                send_reset_email(user)
            except Exception:
                # Never log credentials, email content or reset tokens.
                current_app.logger.error("Échec de l'envoi du mail de réinitialisation ; vérifier le service SMTP.")
        flash("Si un compte actif correspond à cet email, vous recevrez un lien de réinitialisation. Vérifiez aussi vos courriers indésirables.", "info")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = get_reset_user(token)
    if user is None:
        return render_template("auth/reset_password.html", valid=False), 400
    if request.method == "POST":
        password = (request.form.get("password") or "").strip()
        confirmation = (request.form.get("password_confirm") or "").strip()
        if len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "danger")
        elif len(password) > 256:
            flash("Le mot de passe ne doit pas dépasser 256 caractères.", "danger")
        elif password != confirmation:
            flash("Les mots de passe ne correspondent pas.", "danger")
        else:
            # Compare-and-swap also prevents simultaneous reuse of the same link.
            changed = User.query.filter_by(id=user.id, password_hash=user.password_hash, is_active=True).update(
                {"password_hash": generate_password_hash(password)}, synchronize_session=False
            )
            db.session.commit()
            if not changed:
                return render_template("auth/reset_password.html", valid=False), 400
            logout_user()
            flash("Mot de passe mis à jour. Connectez-vous avec votre nouveau mot de passe.", "success")
            return redirect(url_for("auth.login_get"))
    return render_template("auth/reset_password.html", valid=True)


@bp.after_request
def protect_reset_pages(response):
    if request.endpoint in {"auth.reset_password", "auth.forgot_password"}:
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
    return response


def _redirect_for_user(user):
    endpoint = "admin.clients_list" if user.role == "admin" else "client.dashboard"
    return redirect(url_for(endpoint))


@bp.get("/register")
def register_get():
    if current_user.is_authenticated:
        return _redirect_for_user(current_user)
    return render_template("auth/register.html")


@bp.post("/register")
def register_post():
    db.session.rollback()
    if current_user.is_authenticated:
        return _redirect_for_user(current_user)

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    if not email or not password:
        flash("Email et mot de passe obligatoires.", "danger")
        return redirect(url_for("auth.register_get"))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash("Cet email existe déjà. Connecte-toi.", "warning")
        return redirect(url_for("auth.login_get"))

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="client",
    )
    db.session.add(user)
    db.session.commit()

    flash("Compte créé avec succès ✅", "success")
    return redirect(url_for("auth.login_get"))


@bp.get("/login")
def login_get():
    if current_user.is_authenticated:
        return _redirect_for_user(current_user)
    return render_template("auth/login.html")


@bp.post("/login")
def login_post():
    db.session.rollback()
    if current_user.is_authenticated:
        return _redirect_for_user(current_user)

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    user = User.query.filter_by(email=email).first()
    if user is None or not check_password_hash(user.password_hash, password):
        flash("Email ou mot de passe incorrect.", "danger")
        return redirect(url_for("auth.login_get"))

    if not login_user(user):
        flash("Ce compte a été désactivé...", "danger")
        return redirect(url_for("auth.login_get"))

    flash("Connecté ✅", "success")
    return _redirect_for_user(user)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Déconnecté.", "info")
    return redirect(url_for("auth.login_get"))
