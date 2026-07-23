import os
from dataclasses import dataclass
from typing import Optional

import cloudinary
import cloudinary.uploader


@dataclass
class UploadedInvitationFiles:
    pdf_url: str
    qr_url: str


def _validate_cloudinary_config() -> None:
    """
    Configure Cloudinary avec les trois variables présentes sur Render.
    """

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    missing_variables = []

    if not cloud_name:
        missing_variables.append("CLOUDINARY_CLOUD_NAME")

    if not api_key:
        missing_variables.append("CLOUDINARY_API_KEY")

    if not api_secret:
        missing_variables.append("CLOUDINARY_API_SECRET")

    if missing_variables:
        raise RuntimeError(
            "Configuration Cloudinary incomplète. "
            "Variables manquantes : "
            + ", ".join(missing_variables)
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def _destroy_uploaded_file(
    public_id: Optional[str],
    *,
    resource_type: str,
) -> None:
    """
    Supprime un fichier Cloudinary déjà envoyé si la suite échoue.
    """

    if not public_id:
        return

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
            invalidate=True,
        )
    except Exception:
        # Le nettoyage ne doit pas masquer l'erreur principale.
        pass


def upload_invitation_files(
    *,
    pdf_path: str,
    qr_path: str,
    event_id: int,
    guest_id: int,
) -> UploadedInvitationFiles:
    """
    Envoie le PDF et le QR vers Cloudinary.
    """

    _validate_cloudinary_config()

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(
            f"PDF local introuvable : {pdf_path}"
        )

    if not os.path.isfile(qr_path):
        raise FileNotFoundError(
            f"QR local introuvable : {qr_path}"
        )

    folder = f"invitation-platforma/events/event_{event_id}"

    pdf_public_id = f"{folder}/pdf/invite_{guest_id}.pdf"
    qr_public_id = f"{folder}/qr/invite_{guest_id}"

    uploaded_pdf_public_id: Optional[str] = None
    uploaded_qr_public_id: Optional[str] = None

    try:
        pdf_result = cloudinary.uploader.upload(
            pdf_path,
            resource_type="raw",
            public_id=pdf_public_id,
            overwrite=True,
            invalidate=True,
        )

        uploaded_pdf_public_id = pdf_result.get("public_id")

        qr_result = cloudinary.uploader.upload(
            qr_path,
            resource_type="image",
            public_id=qr_public_id,
            format="png",
            overwrite=True,
            invalidate=True,
        )

        uploaded_qr_public_id = qr_result.get("public_id")

        pdf_url = pdf_result.get("secure_url")
        qr_url = qr_result.get("secure_url")

        if not pdf_url or not qr_url:
            raise RuntimeError(
                "Cloudinary n'a pas retourné les deux URL sécurisées."
            )

        return UploadedInvitationFiles(
            pdf_url=pdf_url,
            qr_url=qr_url,
        )

    except Exception:
        _destroy_uploaded_file(
            uploaded_pdf_public_id,
            resource_type="raw",
        )

        _destroy_uploaded_file(
            uploaded_qr_public_id,
            resource_type="image",
        )

        raise


def delete_local_generated_files(*paths: str) -> None:
    """
    Supprime les fichiers temporaires locaux après leur traitement.
    """

    for path in paths:
        if not path:
            continue

        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            # Une erreur de nettoyage ne doit pas annuler la génération.
            pass
