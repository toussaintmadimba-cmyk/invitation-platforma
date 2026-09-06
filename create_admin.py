import argparse

from platform_app import create_app, db
from platform_app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attribue le rôle administrateur à un utilisateur existant."
    )
    parser.add_argument("email", help="Adresse email du compte à promouvoir")
    args = parser.parse_args()

    email = args.email.strip().lower()
    app = create_app()

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            print(f"Utilisateur introuvable : {email}")
            return 1

        user.role = "admin"
        db.session.commit()

    print(f"Administrateur créé : {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
