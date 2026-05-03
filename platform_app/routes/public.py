from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from .. import db
from ..models import Invitation, RSVP


bp = Blueprint("public", __name__)


@bp.get("/")
def home():
    return redirect(url_for("auth.login_get"))


def _get_invitation_or_404(code: str) -> Invitation:
    invitation = Invitation.query.filter_by(invitation_code=code).first()
    if invitation is None:
        abort(404)
    return invitation


@bp.get("/i/<string:code>")
def invitation_page(code: str):
    invitation = _get_invitation_or_404(code)

    rsvp = RSVP.query.filter_by(invitation_id=invitation.id).first()

    return render_template(
        "public/invitation.html",
        inv=invitation,
        event=invitation.event,
        guest=invitation.guest,
        status=rsvp.status if rsvp else "pending",
        message=rsvp.message if rsvp else "",
    )


@bp.route("/i/<string:code>/rsvp", methods=["GET", "POST"])
def invitation_rsvp(code: str):
    invitation = _get_invitation_or_404(code)

    status = (request.form.get("status") or request.args.get("status") or "").strip().lower()
    message = (request.form.get("message") or request.args.get("message") or "").strip()

    if status not in ("yes", "no"):
        flash("Merci de choisir une réponse.", "warning")
        return redirect(url_for("public.invitation_page", code=code))

    rsvp = RSVP.query.filter_by(invitation_id=invitation.id).first()

    if rsvp is None:
        rsvp = RSVP(invitation_id=invitation.id)

    rsvp.status = status
    rsvp.message = message or None
    rsvp.responded_at = datetime.utcnow()

    db.session.add(rsvp)
    db.session.commit()

    return redirect(url_for("public.rsvp_thanks", code=code))


@bp.get("/i/<string:code>/merci")
def rsvp_thanks(code: str):
    invitation = _get_invitation_or_404(code)

    rsvp = RSVP.query.filter_by(invitation_id=invitation.id).first()

    return render_template(
        "public/rsvp_thanks.html",
        inv=invitation,
        event=invitation.event,
        guest=invitation.guest,
        rsvp=rsvp,
    )