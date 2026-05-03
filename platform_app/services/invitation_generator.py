import os
import re
import secrets
from typing import Dict

from .. import db
from ..models import Guest, Invitation
from .template_renderer import TemplateRenderer


def generate_all_invitations_for_event(
    *,
    event,
    storage_dir: str,
    base_public_url: str,
) -> Dict[str, int]:
    template_id = getattr(event, "template_id", None) or "template_001"

    guests = Guest.query.filter_by(event_id=event.id).all()

    pdf_dir = os.path.join(storage_dir, "pdf", f"event_{event.id}")
    qr_dir = os.path.join(storage_dir, "qr", f"event_{event.id}")

    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(qr_dir, exist_ok=True)

    renderer = TemplateRenderer(storage_dir=storage_dir)

    files_generated = 0

    for guest in guests:
        invitation = Invitation.query.filter_by(
            event_id=event.id,
            guest_id=guest.id,
        ).first()

        if invitation is None:
            invitation = Invitation(
                event_id=event.id,
                guest_id=guest.id,
            )

        if not invitation.invitation_code:
            invitation.invitation_code = secrets.token_urlsafe(24)

        filename_base = _build_invitation_filename_base(event=event, guest=guest)

        pdf_path = os.path.join(pdf_dir, f"{filename_base}.pdf")
        qr_path = os.path.join(qr_dir, f"{filename_base}.png")

        variables = _build_template_variables(guest)

        renderer.render_invitation(
            template_id=template_id,
            variables=variables,
            invitation_code=invitation.invitation_code,
            base_public_url=base_public_url,
            pdf_path=pdf_path,
            qr_path=qr_path,
        )

        invitation.pdf_path = pdf_path
        invitation.qr_path = qr_path

        db.session.add(invitation)
        files_generated += 1

    db.session.commit()

    return {
        "files_generated": files_generated,
    }


def _build_template_variables(guest: Guest) -> Dict[str, str]:
    """
    Champs dynamiques autorisés côté métier :
    - civility
    - guest_name
    - table
    - guest_label
    - table_label

    Le reste reste figé dans les PNG du design.
    """

    civility = _normalize_civility(getattr(guest, "civility", None))
    guest_name = _clean(getattr(guest, "full_name", ""))
    table = _clean(getattr(guest, "table_name", ""))

    guest_label = f"{civility} {guest_name}".strip() if guest_name else civility
    table_label = f"Table : {table}" if table else ""

    return {
        "civility": civility,
        "guest_name": guest_name,
        "table": table,
        "guest_label": guest_label,
        "table_label": table_label,
    }


def _normalize_civility(value) -> str:
    value = _clean(value).upper()

    mapping = {
        "MR": "MR",
        "M": "MR",
        "MONSIEUR": "MR",
        "MME": "MME",
        "MADAME": "MME",
        "MLLE": "MLLE",
        "MADEMOISELLE": "MLLE",
        "COUPLE": "COUPLE",
    }

    return mapping.get(value, "MME")


def _build_invitation_filename_base(*, event, guest: Guest) -> str:
    event_title = _clean(getattr(event, "title", "")) or f"event_{event.id}"
    civility = _normalize_civility(getattr(guest, "civility", None))
    guest_name = _clean(getattr(guest, "full_name", "")) or f"guest_{guest.id}"
    table = _clean(getattr(guest, "table_name", ""))

    parts = [
        event_title,
        civility,
        guest_name,
    ]

    if table:
        parts.append(f"table-{table}")

    return _slugify(" ".join(parts))


def _clean(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _slugify(value: str) -> str:
    value = _clean(value).lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value, flags=re.UNICODE)
    value = value.strip("-")
    return value or "invitation"