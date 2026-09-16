"""Configuration diagnostics without database access or printing secrets."""
import argparse
import os
from email.message import EmailMessage

from platform_app.config import Config, validate_production_config
from platform_app.services.password_reset import validate_mail_config, send_email


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-test", metavar="EMAIL", help="Envoyer explicitement un email de test à cette adresse")
    args = parser.parse_args()
    config = {key: getattr(Config, key) for key in dir(Config) if key.isupper()}
    valid = True
    for name in ("MAIL_HOST", "MAIL_FROM", "MAIL_USERNAME", "MAIL_PASSWORD",
                 "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
                 "SECRET_KEY", "DATABASE_URL", "BASE_PUBLIC_URL"):
        print(name + ": " + ("présent" if os.environ.get(name) else "absent"))
    for label, check in (("SMTP", validate_mail_config), ("Production", validate_production_config)):
        try:
            check(config)
            print(label + ": configuration valide" if label != "Production" or config["APP_ENV"] == "production" else "Production : non évaluée (mode local)")
        except RuntimeError:
            print(label + ": configuration incomplète ou incohérente ; consulter FEATURE_NOTES.md")
            valid = False
    if not all(os.environ.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")):
        valid = False
    if args.send_test:
        message = EmailMessage()
        message["Subject"] = "Test d’envoi — Invitations"
        message["From"] = config["MAIL_FROM"]
        message["To"] = args.send_test
        message.set_content("L’envoi SMTP de la plateforme fonctionne. Ce message ne contient aucun lien de récupération.")
        try:
            send_email(message, config)
            print("Message accepté par le serveur SMTP. Vérifiez sa réception et les indésirables.")
        except Exception:
            print("Échec du test SMTP. Vérifiez les paramètres et la connectivité ; aucun secret affiché.")
            return 1
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
