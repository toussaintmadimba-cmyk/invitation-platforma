import os
from typing import Dict

import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .. import db
from ..models import Guest, Invitation


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe(value) -> str:
    return "" if value is None else str(value).strip()


def _make_qr_png(save_path: str, data: str) -> None:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(save_path)


def _guest_label(guest: Guest) -> str:
    civility = _safe(getattr(guest, "civility", "")) or "MME"
    name = _safe(getattr(guest, "full_name", ""))
    return f"{civility} {name}".strip()


def _table_label(guest: Guest) -> str:
    table = _safe(getattr(guest, "table_name", ""))
    return f"Table : {table}" if table else ""


def _render_light_pdf(
    *,
    guest: Guest,
    event,
    invitation_code: str,
    base_public_url: str,
    pdf_path: str,
    qr_path: str,
) -> None:
    base = (base_public_url or "").rstrip("/")
    invite_url = f"{base}/i/{invitation_code}" if base else f"/i/{invitation_code}"

    _ensure_dir(os.path.dirname(pdf_path))
    _ensure_dir(os.path.dirname(qr_path))

    _make_qr_png(qr_path, invite_url)

    page_w, page_h = A5
    c = canvas.Canvas(pdf_path, pagesize=A5)

    # Page 1
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w / 2, page_h - 45 * mm, "INVITATION")

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h - 65 * mm, _safe(event.title))

    c.setFont("Helvetica", 12)
    c.drawCentredString(
        page_w / 2,
        page_h - 78 * mm,
        event.event_datetime.strftime("%d/%m/%Y à %H:%M"),
    )

    c.setFont("Helvetica", 12)
    c.drawCentredString(page_w / 2, page_h - 100 * mm, "Cher invité,")

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h - 112 * mm, _guest_label(guest))

    table = _table_label(guest)
    if table:
        c.setFont("Helvetica", 12)
        c.drawCentredString(page_w / 2, page_h - 125 * mm, table)

    c.setFont("Helvetica", 11)
    c.drawCentredString(page_w / 2, 58 * mm, "Scannez ce QR code pour confirmer votre présence")

    if os.path.exists(qr_path):
        c.drawImage(
            ImageReader(qr_path),
            (page_w - 35 * mm) / 2,
            20 * mm,
            width=35 * mm,
            height=35 * mm,
            mask="auto",
        )

    c.showPage()
    c.save()


def generate_all_invitations_for_event(
    *,
    event,
    storage_dir: str,
    base_public_url: str,
) -> Dict[str, int]:
    guests = Guest.query.filter_by(event_id=event.id).all()

    pdf_dir = os.path.join(storage_dir, "pdf", f"event_{event.id}")
    qr_dir = os.path.join(storage_dir, "qr", f"event_{event.id}")

    _ensure_dir(pdf_dir)
    _ensure_dir(qr_dir)

    files_generated = 0

    for guest in guests:
        inv = Invitation.query.filter_by(
            event_id=event.id,
            guest_id=guest.id,
        ).first()

        if inv is None:
            inv = Invitation(event_id=event.id, guest_id=guest.id)

        if not inv.invitation_code:
            inv.invitation_code = os.urandom(16).hex()

        pdf_path = os.path.join(pdf_dir, f"invite_{guest.id}.pdf")
        qr_path = os.path.join(qr_dir, f"invite_{guest.id}.png")

        _render_light_pdf(
            guest=guest,
            event=event,
            invitation_code=inv.invitation_code,
            base_public_url=base_public_url,
            pdf_path=pdf_path,
            qr_path=qr_path,
        )

        inv.pdf_path = pdf_path
        inv.qr_path = qr_path

        db.session.add(inv)
        files_generated += 1

    db.session.commit()

    return {"files_generated": files_generated}