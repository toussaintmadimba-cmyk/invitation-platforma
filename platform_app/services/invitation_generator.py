import os
from typing import Any, Dict, Optional

from flask import current_app

from .. import db
from ..models import Guest, Invitation
from .template_renderer import TemplateRenderer
from .cloud_storage import (
    delete_local_generated_files,
    upload_invitation_files,
)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe(value) -> str:
    return "" if value is None else str(value).strip()


def generate_all_invitations_for_event(
    *,
    event,
    storage_dir: str,
    base_public_url: str,
    offset: int = 0,
    limit: int = 20,
    force: bool = False,
) -> Dict[str, Any]:
    offset = max(offset, 0)
    limit = max(limit, 1)

    guests_query = Guest.query.filter_by(event_id=event.id).order_by(Guest.id.asc())
    total_guests = guests_query.count()
    guests = guests_query.offset(offset).limit(limit).all()
    next_offset: Optional[int] = offset + limit
    if next_offset >= total_guests:
        next_offset = None

    pdf_dir = os.path.join(storage_dir, "pdf", f"event_{event.id}")
    qr_dir = os.path.join(storage_dir, "qr", f"event_{event.id}")

    _ensure_dir(pdf_dir)
    _ensure_dir(qr_dir)

    renderer = TemplateRenderer(storage_dir)
    files_generated = 0
    errors = 0

    for index, guest in enumerate(guests, start=1):
        invitation = Invitation.query.filter_by(
            event_id=event.id,
            guest_id=guest.id,
        ).first()

        if invitation is None:
            invitation = Invitation(
                event_id=event.id,
                guest_id=guest.id,
            )

        if (
            not force
            and invitation.pdf_path
            and invitation.qr_path
        ):
            continue

        if not invitation.invitation_code:
            invitation.invitation_code = os.urandom(16).hex()

        pdf_path = os.path.join(pdf_dir, f"invite_{guest.id}.pdf")
        qr_path = os.path.join(qr_dir, f"invite_{guest.id}.png")

        civility = _safe(getattr(guest, "civility", ""))
        full_name = _safe(guest.full_name)
        table_name = _safe(getattr(guest, "table_name", ""))

        try:
            renderer.render_invitation(
                template_id="template_001",
                variables={
                    "guest_label": f"{civility} {full_name}".strip(),
                    "table_label": f"Table {table_name}" if table_name else "",
                },
                invitation_code=invitation.invitation_code,
                base_public_url=base_public_url,
                pdf_path=pdf_path,
                qr_path=qr_path,
            )
            uploaded_files = upload_invitation_files(
                pdf_path=pdf_path,
                qr_path=qr_path,
                event_id=event.id,
                guest_id=guest.id,
            )
            invitation.pdf_path = uploaded_files.pdf_url
            invitation.qr_path = uploaded_files.qr_url
            
        except Exception as exc:
            errors += 1
            current_app.logger.error(
                "Erreur génération invitation invité %s: %s",
                guest.id,
                exc,
                exc_info=True,
            )
            db.session.rollback()
            continue
        finally:
            delete_local_generated_files(
                pdf_path,
                qr_path,
            )

        db.session.add(invitation)
        files_generated += 1

        if index % 20 == 0:
            db.session.commit()

    db.session.commit()

    return {
        "files_generated": files_generated,
        "errors": errors,
        "total_guests": total_guests,
        "next_offset": next_offset,
    }
