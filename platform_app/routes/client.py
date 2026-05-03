import os
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, send_file
from flask_login import login_required, current_user

from .. import db
from ..models import Event, Guest, Invitation, RSVP
from ..services.invitation_generator import generate_all_invitations_for_event


bp = Blueprint("client", __name__, url_prefix="/client")


def _require_client():
    if getattr(current_user, "role", None) != "client":
        abort(403)


def _get_client_event_or_404(event_id: int) -> Event:
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    return event


def _resolve_file_path(path_in_db: str) -> str:
    if not path_in_db:
        return ""

    storage_root = os.path.abspath(current_app.config["STORAGE_DIR"])
    path_in_db = str(path_in_db)

    token = os.path.join("platform_app", "storage")
    if token in path_in_db:
        tail = path_in_db.split(token, 1)[1].lstrip("\\/")
        return os.path.join(storage_root, tail)

    storage_token = os.path.sep + "storage" + os.path.sep
    if storage_token in path_in_db:
        tail = path_in_db.split(storage_token, 1)[1]
        return os.path.join(storage_root, tail)

    if not os.path.isabs(path_in_db):
        return os.path.join(storage_root, path_in_db)

    return path_in_db


def _safe_download_name(value: str) -> str:
    value = value or "fichier"
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        value = value.replace(char, " ")
    return " ".join(value.split()).strip()


# ---------------- DASHBOARD ----------------

@bp.get("/dashboard")
@login_required
def dashboard():
    _require_client()

    events = Event.query.filter_by(user_id=current_user.id).order_by(Event.created_at.desc()).all()

    total_events = len(events)
    total_guests = sum(Guest.query.filter_by(event_id=e.id).count() for e in events)
    active_events = sum(1 for e in events if e.is_active)

    return render_template(
        "client/dashboard.html",
        events=events,
        total_events=total_events,
        total_guests=total_guests,
        active_events=active_events,
    )


# ---------------- EVENTS ----------------

@bp.get("/events")
@login_required
def events_list():
    _require_client()

    events = Event.query.filter_by(user_id=current_user.id).order_by(Event.created_at.desc()).all()
    return render_template("client/events.html", events=events)


@bp.post("/events")
@login_required
def events_create():
    _require_client()

    title = (request.form.get("title") or "").strip()
    event_datetime_raw = (request.form.get("event_datetime") or "").strip()
    location_name = (request.form.get("location_name") or "").strip()
    address = (request.form.get("address") or "").strip()

    instructions = (request.form.get("instructions") or "").strip()

    if not title or not event_datetime_raw or not location_name or not address:
        flash("Titre, date/heure, lieu et adresse sont obligatoires.", "danger")
        return redirect(url_for("client.events_list"))

    try:
        event_datetime = datetime.strptime(event_datetime_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("Format date/heure invalide.", "danger")
        return redirect(url_for("client.events_list"))

    event = Event(
        user_id=current_user.id,
        title=title,
        event_datetime=event_datetime,
        location_name=location_name,
        address=address,
        show_location=bool(request.form.get("show_location")),
        show_program=bool(request.form.get("show_program")),
        show_contacts=bool(request.form.get("show_contacts")),
        show_instructions=bool(request.form.get("show_instructions")),
        instructions=instructions or None,
        is_active=bool(request.form.get("is_active")),
    )

    db.session.add(event)
    db.session.commit()

    flash("Événement créé ✅", "success")
    return redirect(url_for("client.events_list"))


@bp.get("/events/<int:event_id>/edit")
@login_required
def events_edit_get(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)
    return render_template("client/event_edit.html", event=event)


@bp.post("/events/<int:event_id>/edit")
@login_required
def events_edit_post(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)

    title = (request.form.get("title") or "").strip()
    event_datetime_raw = (request.form.get("event_datetime") or "").strip()
    location_name = (request.form.get("location_name") or "").strip()
    address = (request.form.get("address") or "").strip()
    instructions = (request.form.get("instructions") or "").strip()

    if not title or not event_datetime_raw or not location_name or not address:
        flash("Titre, date/heure, lieu et adresse sont obligatoires.", "danger")
        return redirect(url_for("client.events_edit_get", event_id=event.id))

    try:
        event_datetime = datetime.strptime(event_datetime_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("Format date/heure invalide.", "danger")
        return redirect(url_for("client.events_edit_get", event_id=event.id))

    event.title = title
    event.event_datetime = event_datetime
    event.location_name = location_name
    event.address = address
    event.show_location = bool(request.form.get("show_location"))
    event.show_program = bool(request.form.get("show_program"))
    event.show_contacts = bool(request.form.get("show_contacts"))
    event.show_instructions = bool(request.form.get("show_instructions"))
    event.instructions = instructions or None
    event.is_active = bool(request.form.get("is_active"))

    db.session.commit()

    flash("Événement mis à jour ✅", "success")
    return redirect(url_for("client.events_list"))


# ---------------- GUESTS ----------------

@bp.get("/events/<int:event_id>/guests")
@login_required
def guests_list(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)

    guests = Guest.query.filter_by(event_id=event.id).order_by(Guest.created_at.desc()).all()
    invitations_count = Invitation.query.filter_by(event_id=event.id).count()

    invitation_ids = [
        inv.id for inv in Invitation.query.filter_by(event_id=event.id).all()
    ]

    yes_count = 0
    no_count = 0
    pending_count = invitations_count

    if invitation_ids:
        yes_count = RSVP.query.filter(
            RSVP.invitation_id.in_(invitation_ids),
            RSVP.status == "yes"
        ).count()

        no_count = RSVP.query.filter(
            RSVP.invitation_id.in_(invitation_ids),
            RSVP.status == "no"
        ).count()

        pending_count = max(invitations_count - yes_count - no_count, 0)

    rsvp_stats = {
        "yes": yes_count,
        "no": no_count,
        "pending": pending_count,
    }

    return render_template(
        "client/guests.html",
        event=event,
        guests=guests,
        invitations_count=invitations_count,
        rsvp_stats=rsvp_stats,
    )

@bp.post("/events/<int:event_id>/guests")
@login_required
def guests_create(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)

    full_name = (request.form.get("full_name") or "").strip()

    civility = (request.form.get("civility") or "").strip().upper()
    if civility not in ("MR", "MME", "MLLE", "COUPLE"):
        civility = "MME"

    guest_type = (request.form.get("guest_type") or "").strip().lower()
    if guest_type not in ("single", "couple", "family"):
        guest_type = "single"

    party_size_raw = (request.form.get("party_size") or "").strip()
    table_name = (request.form.get("table_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    email = (request.form.get("email") or "").strip()
    notes = (request.form.get("notes") or "").strip()

    if not full_name:
        flash("Le nom complet est obligatoire.", "danger")
        return redirect(url_for("client.guests_list", event_id=event.id))

    try:
        party_size = int(party_size_raw) if party_size_raw else None
    except ValueError:
        flash("Le nombre de personnes doit être un nombre.", "danger")
        return redirect(url_for("client.guests_list", event_id=event.id))

    if guest_type == "single":
        party_size = 1
    elif guest_type == "couple":
        party_size = party_size or 2
    elif guest_type == "family":
        party_size = party_size or 3

    guest = Guest(
        event_id=event.id,
        civility=civility,
        full_name=full_name,
        guest_type=guest_type,
        party_size=party_size,
        table_name=table_name or None,
        phone=phone or None,
        email=email or None,
        notes=notes or None,
    )

    db.session.add(guest)
    db.session.commit()

    flash("Invité ajouté avec succès ✅", "success")
    return redirect(url_for("client.guests_list", event_id=event.id))


@bp.post("/guests/<int:guest_id>/delete")
@login_required
def guests_delete(guest_id: int):
    _require_client()

    guest = Guest.query.get_or_404(guest_id)

    if guest.event.user_id != current_user.id:
        abort(403)

    invitation = Invitation.query.filter_by(guest_id=guest.id).first()
    if invitation:
        db.session.delete(invitation)

    event_id = guest.event_id

    db.session.delete(guest)
    db.session.commit()

    flash("Invité supprimé ✅", "success")
    return redirect(url_for("client.guests_list", event_id=event_id))


# ---------------- INVITATIONS ----------------

@bp.post("/events/<int:event_id>/invitations/generate-ui")
@login_required
def invitations_generate_ui(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)

    guests_count = Guest.query.filter_by(event_id=event.id).count()
    if guests_count == 0:
        flash("Aucun invité. Ajoute des invités avant de générer.", "warning")
        return redirect(url_for("client.guests_list", event_id=event.id))

    summary = generate_all_invitations_for_event(
        event=event,
        storage_dir=current_app.config["STORAGE_DIR"],
        base_public_url=current_app.config["BASE_PUBLIC_URL"],
    )

    flash(f"Invitations générées ✅ ({summary['files_generated']} fichier(s))", "success")
    return redirect(url_for("client.invitations_list", event_id=event.id))


@bp.get("/events/<int:event_id>/invitations")
@login_required
def invitations_list(event_id: int):
    _require_client()

    event = _get_client_event_or_404(event_id)

    guests = Guest.query.filter_by(event_id=event.id).order_by(Guest.created_at.desc()).all()
    base_public_url = current_app.config["BASE_PUBLIC_URL"].rstrip("/")

    return render_template(
        "client/invitations.html",
        event=event,
        guests=guests,
        base_public_url=base_public_url,
    )


@bp.get("/invitations/<int:inv_id>/pdf")
@login_required
def invitation_download_pdf(inv_id: int):
    _require_client()

    invitation = Invitation.query.get_or_404(inv_id)

    if invitation.event.user_id != current_user.id:
        abort(403)

    real_path = _resolve_file_path(invitation.pdf_path)

    if not real_path or not os.path.exists(real_path):
        flash("PDF introuvable. Regénère les invitations.", "warning")
        return redirect(url_for("client.invitations_list", event_id=invitation.event_id))

    event_title = invitation.event.title if invitation.event else f"event_{invitation.event_id}"
    guest_name = invitation.guest.full_name if invitation.guest else f"invite_{invitation.guest_id}"
    civility = getattr(invitation.guest, "civility", "") if invitation.guest else ""
    table_name = invitation.guest.table_name if invitation.guest else ""

    download_name = _safe_download_name(
        f"{event_title} - {civility} {guest_name}"
        + (f" - Table {table_name}" if table_name else "")
    ) + ".pdf"

    return send_file(real_path, as_attachment=True, download_name=download_name)


@bp.get("/invitations/<int:inv_id>/qr")
@login_required
def invitation_download_qr(inv_id: int):
    _require_client()

    invitation = Invitation.query.get_or_404(inv_id)

    if invitation.event.user_id != current_user.id:
        abort(403)

    real_path = _resolve_file_path(invitation.qr_path)

    if not real_path or not os.path.exists(real_path):
        flash("QR introuvable. Regénère les invitations.", "warning")
        return redirect(url_for("client.invitations_list", event_id=invitation.event_id))

    guest_name = invitation.guest.full_name if invitation.guest else f"invite_{invitation.guest_id}"
    download_name = _safe_download_name(f"QR - {guest_name}") + ".png"

    return send_file(real_path, as_attachment=True, download_name=download_name)