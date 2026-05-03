from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from .. import db
from ..models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.get("/register")
def register_get():
    if current_user.is_authenticated:
        return redirect(url_for("client.dashboard"))
    return render_template("auth/register.html")


@bp.post("/register")
def register_post():
    if current_user.is_authenticated:
        return redirect(url_for("client.dashboard"))

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
        return redirect(url_for("client.dashboard"))
    return render_template("auth/login.html")


@bp.post("/login")
def login_post():
    if current_user.is_authenticated:
        return redirect(url_for("client.dashboard"))

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    user = User.query.filter_by(email=email).first()
    if user is None or not check_password_hash(user.password_hash, password):
        flash("Email ou mot de passe incorrect.", "danger")
        return redirect(url_for("auth.login_get"))

    login_user(user)
    flash("Connecté ✅", "success")
    return redirect(url_for("client.dashboard"))


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Déconnecté.", "info")
    return redirect(url_for("auth.login_get"))
