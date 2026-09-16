import os
from tempfile import TemporaryDirectory
from typing import Any, Dict

from flask import current_app
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Guest, Invitation
from .template_renderer import TemplateRenderer
from .cloud_storage import upload_invitation_files, delete_uploaded_invitation_files


def generate_all_invitations_for_event(
    *, event, storage_dir: str, base_public_url: str,
    offset: int = 0, limit: int = 20, force: bool = False,
) -> Dict[str, Any]:
    offset = max(offset, 0)
    limit = min(max(limit, 1), 50)
    event_id = event.id
    query = Guest.query.filter_by(event_id=event_id).order_by(Guest.id.asc())
    total_guests = query.count()
    guest_ids = [g.id for g in query.offset(offset).limit(limit).all()]
    next_offset = offset + limit if offset + limit < total_guests else None
    renderer = TemplateRenderer(storage_dir)
    temp_root = os.path.join(storage_dir, "tmp")
    os.makedirs(temp_root, exist_ok=True)
    files_generated = errors = 0

    for guest_id in guest_ids:
        uploaded = None
        try:
            guest = db.session.get(Guest, guest_id)
            if guest is None:
                raise ValueError("Guest removed during generation")
            invitation = Invitation.query.filter_by(guest_id=guest_id).first()
            if invitation is None:
                # Reserve a stable code before external work. Failed uploads are retryable.
                invitation = Invitation(event_id=event_id, guest_id=guest_id,
                                        invitation_code=os.urandom(16).hex())
                db.session.add(invitation)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    invitation = Invitation.query.filter_by(guest_id=guest_id).one()
            if not force and invitation.pdf_path and invitation.qr_path:
                continue
            invitation_id = invitation.id
            old_pdf, old_qr = invitation.pdf_path, invitation.qr_path
            code = invitation.invitation_code
            variables = {
                "guest_label": f"{guest.civility or ''} {guest.full_name}".strip(),
                "table_label": f"Table {guest.table_name}" if guest.table_name else "",
            }
            # Release the read transaction before rendering/network I/O.
            db.session.commit()
            with TemporaryDirectory(dir=temp_root) as temp_dir:
                pdf_path = os.path.join(temp_dir, "invitation.pdf")
                qr_path = os.path.join(temp_dir, "qr.png")
                renderer.render_invitation(
                    template_id="template_001", variables=variables,
                    invitation_code=code, base_public_url=base_public_url,
                    pdf_path=pdf_path, qr_path=qr_path,
                )
                uploaded = upload_invitation_files(
                    pdf_path=pdf_path, qr_path=qr_path,
                    event_id=event_id, guest_id=guest_id,
                )
                changed = Invitation.query.filter_by(
                    id=invitation_id, pdf_path=old_pdf, qr_path=old_qr,
                ).update({"pdf_path": uploaded.pdf_url, "qr_path": uploaded.qr_url},
                         synchronize_session=False)
                if changed != 1:
                    raise RuntimeError("Invitation changed during generation; retry")
                db.session.commit()
                files_generated += 1
                uploaded = None
        except Exception:
            db.session.rollback()
            if uploaded is not None:
                delete_uploaded_invitation_files(uploaded)
            errors += 1
            current_app.logger.error("Generation failed for guest %s; retry batch.", guest_id)

    return {"files_generated": files_generated, "errors": errors,
            "total_guests": total_guests, "next_offset": next_offset}
