import os
from typing import Dict

from .. import db
from ..models import Guest, Invitation


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe(value) -> str:
    return "" if value is None else str(value).strip()


def _write_minimal_pdf(path: str, title: str, guest_name: str, invite_url: str) -> None:
    """
    PDF minimal sans ReportLab, sans Pillow, sans image.
    Objectif : fonctionner sur Render sans 502.
    """

    content = f"""BT
/F1 22 Tf
70 760 Td
(INVITATION) Tj
0 -40 Td
/F1 14 Tf
({title}) Tj
0 -30 Td
({guest_name}) Tj
0 -40 Td
(Confirmez votre presence ici :) Tj
0 -25 Td
({invite_url}) Tj
ET
"""

    content_bytes = content.encode("latin-1", errors="replace")

    objects = []

    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> "
        b"/Contents 5 0 R >>\n"
        b"endobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n"
        + f"<< /Length {len(content_bytes)} >>\n".encode("ascii")
        + b"stream\n"
        + content_bytes
        + b"\nendstream\nendobj\n"
    )

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")

    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_position = len(pdf)

    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n".encode("ascii")
    )

    with open(path, "wb") as file:
        file.write(pdf)


def _write_qr_placeholder(path: str, invite_url: str) -> None:
    """
    Fichier placeholder temporaire.
    On remettra le vrai QR après stabilisation Render.
    """
    with open(path, "w", encoding="utf-8") as file:
        file.write(invite_url)


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
            invitation.invitation_code = os.urandom(16).hex()

        invite_url = f"{base_public_url.rstrip()}/i/{invitation.invitation_code}"

        pdf_path = os.path.join(pdf_dir, f"invite_{guest.id}.pdf")
        qr_path = os.path.join(qr_dir, f"invite_{guest.id}.txt")

        guest_name = f"{_safe(getattr(guest, 'civility', ''))} {_safe(guest.full_name)}".strip()

        _write_minimal_pdf(
            path=pdf_path,
            title=_safe(event.title),
            guest_name=guest_name,
            invite_url=invite_url,
        )

        _write_qr_placeholder(
            path=qr_path,
            invite_url=invite_url,
        )

        invitation.pdf_path = pdf_path
        invitation.qr_path = qr_path

        db.session.add(invitation)
        files_generated += 1

    db.session.commit()

    return {"files_generated": files_generated}