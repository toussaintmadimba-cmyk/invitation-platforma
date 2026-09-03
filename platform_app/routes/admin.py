from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import func

from .. import db
from ..models import Event, User


bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


@bp.get("/clients")
@admin_required
def clients_list():
    clients = (
        db.session.query(User, func.count(Event.id).label("event_count"))
        .outerjoin(Event, Event.user_id == User.id)
        .filter(User.role == "client")
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .all()
    )
    return render_template("admin/clients.html", clients=clients)


@bp.post("/clients/<int:user_id>/toggle-access")
@admin_required
def toggle_client_access(user_id: int):
    user = db.session.get(User, user_id)
    if user is None or user.role != "client":
        abort(404)

    user.is_active = not user.is_active
    db.session.commit()

    status = "réactivé" if user.is_active else "suspendu"
    flash(f"Le compte {user.email} a été {status}.", "success")
    return redirect(url_for("admin.clients_list"))
