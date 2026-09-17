"""Phase 1 database baseline.

This revision supports both a new database and the legacy SQLite/PostgreSQL
schema previously created with ``db.create_all()``. Existing business rows are
updated in place; the obsolete ``partner_name`` column is removed only when it
contains no value.

Revision ID: 28d6db2cbd97
Revises: 
Create Date: 2026-09-16 23:47:04.450440

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '28d6db2cbd97'
down_revision = None
branch_labels = None
depends_on = None


BUSINESS_TABLES = {"user", "event", "guest", "invitation", "rsvp"}


def _create_schema():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("event_datetime", sa.DateTime(), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("show_location", sa.Boolean(), nullable=True),
        sa.Column("show_program", sa.Boolean(), nullable=True),
        sa.Column("show_contacts", sa.Boolean(), nullable=True),
        sa.Column("show_instructions", sa.Boolean(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "guest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("civility", sa.String(length=10), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("guest_type", sa.String(length=20), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("party_size BETWEEN 1 AND 100", name="ck_guest_party_size"),
        sa.CheckConstraint(
            "(guest_type = 'single' AND party_size = 1) OR "
            "(guest_type = 'couple' AND party_size = 2) OR "
            "(guest_type = 'family' AND party_size BETWEEN 2 AND 100)",
            name="ck_guest_type_size",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "invitation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("invitation_code", sa.String(length=80), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("qr_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.ForeignKeyConstraint(["guest_id"], ["guest.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guest_id", name="uq_invitation_guest"),
    )
    op.create_index(
        "ix_invitation_invitation_code",
        "invitation",
        ["invitation_code"],
        unique=True,
    )

    op.create_table(
        "rsvp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invitation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitation.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_id"),
    )


def _column_map(bind, table):
    return {column["name"]: column for column in inspect(bind).get_columns(table)}


def _backfill_user_names(bind):
    rows = bind.execute(sa.text(
        'SELECT id, email, name FROM "user" WHERE name IS NULL OR trim(name) = :empty'
    ), {"empty": ""}).mappings()
    for row in rows:
        email = (row["email"] or "").strip()
        fallback = email.split("@", 1)[0] or email or f"Utilisateur {row['id']}"
        bind.execute(
            sa.text('UPDATE "user" SET name = :name WHERE id = :id'),
            {"name": fallback[:255], "id": row["id"]},
        )


def _upgrade_existing_schema(bind):
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    missing = BUSINESS_TABLES - tables
    if missing:
        raise RuntimeError(
            "Migration refusée : tables métier manquantes : " + ", ".join(sorted(missing))
        )

    guest_columns = _column_map(bind, "guest")
    if "partner_name" in guest_columns:
        used_partner_names = bind.execute(sa.text(
            "SELECT count(*) FROM guest "
            "WHERE partner_name IS NOT NULL AND trim(partner_name) <> :empty"
        ), {"empty": ""}).scalar_one()
        if used_partner_names:
            raise RuntimeError(
                "Migration refusée : guest.partner_name contient des données. "
                "Décidez explicitement où les conserver avant de relancer."
            )

    invalid_groups = bind.execute(sa.text(
        "SELECT count(*) FROM guest WHERE guest_type IS NULL OR party_size IS NULL OR NOT ("
        "(guest_type = 'single' AND party_size = 1) OR "
        "(guest_type = 'couple' AND party_size = 2) OR "
        "(guest_type = 'family' AND party_size BETWEEN 2 AND 100))"
    )).scalar_one()
    duplicate_invitations = bind.execute(sa.text(
        "SELECT count(*) FROM (SELECT guest_id FROM invitation GROUP BY guest_id "
        "HAVING count(*) > 1) AS duplicates"
    )).scalar_one()
    if invalid_groups or duplicate_invitations:
        raise RuntimeError(
            "Migration refusée : corrigez d'abord les groupes invalides ou invitations dupliquées."
        )

    user_columns = _column_map(bind, "user")
    if "name" not in user_columns:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(sa.Column("name", sa.String(length=255), nullable=True))
    if "is_active" not in user_columns:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ))
    _backfill_user_names(bind)
    user_columns = _column_map(bind, "user")
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "name",
            existing_type=user_columns["name"]["type"],
            type_=sa.String(length=255),
            existing_nullable=user_columns["name"]["nullable"],
            nullable=False,
        )

    inspector = inspect(bind)
    guest_columns = _column_map(bind, "guest")
    check_names = {
        item.get("name") for item in inspector.get_check_constraints("guest")
    }
    table_name_length = getattr(guest_columns["table_name"]["type"], "length", None)
    dialect = bind.dialect.name

    if dialect == "sqlite":
        table_args = []
        if "ck_guest_party_size" not in check_names:
            table_args.append(sa.CheckConstraint(
                "party_size BETWEEN 1 AND 100", name="ck_guest_party_size"
            ))
        if "ck_guest_type_size" not in check_names:
            table_args.append(sa.CheckConstraint(
                "(guest_type = 'single' AND party_size = 1) OR "
                "(guest_type = 'couple' AND party_size = 2) OR "
                "(guest_type = 'family' AND party_size BETWEEN 2 AND 100)",
                name="ck_guest_type_size",
            ))
        if "partner_name" in guest_columns or table_name_length != 100 or table_args:
            with op.batch_alter_table(
                "guest", recreate="always", table_args=tuple(table_args)
            ) as batch_op:
                if "partner_name" in guest_columns:
                    batch_op.drop_column("partner_name")
                if table_name_length != 100:
                    batch_op.alter_column(
                        "table_name",
                        existing_type=guest_columns["table_name"]["type"],
                        type_=sa.String(length=100),
                        existing_nullable=guest_columns["table_name"]["nullable"],
                    )
    elif dialect == "postgresql":
        with op.batch_alter_table("guest") as batch_op:
            if "partner_name" in guest_columns:
                batch_op.drop_column("partner_name")
            if table_name_length != 100:
                batch_op.alter_column(
                    "table_name",
                    existing_type=guest_columns["table_name"]["type"],
                    type_=sa.String(length=100),
                    existing_nullable=guest_columns["table_name"]["nullable"],
                )
            if "ck_guest_party_size" not in check_names:
                batch_op.create_check_constraint(
                    "ck_guest_party_size", "party_size BETWEEN 1 AND 100"
                )
            if "ck_guest_type_size" not in check_names:
                batch_op.create_check_constraint(
                    "ck_guest_type_size",
                    "(guest_type = 'single' AND party_size = 1) OR "
                    "(guest_type = 'couple' AND party_size = 2) OR "
                    "(guest_type = 'family' AND party_size BETWEEN 2 AND 100)",
                )
    else:
        raise RuntimeError(f"Dialecte non pris en charge : {dialect}")

    inspector = inspect(bind)
    unique_guest = any(
        item.get("column_names") == ["guest_id"]
        for item in inspector.get_unique_constraints("invitation")
    ) or any(
        item.get("unique") and item.get("column_names") == ["guest_id"]
        for item in inspector.get_indexes("invitation")
    )
    if not unique_guest:
        if dialect == "sqlite":
            op.create_index("uq_invitation_guest", "invitation", ["guest_id"], unique=True)
        else:
            op.create_unique_constraint("uq_invitation_guest", "invitation", ["guest_id"])

    legacy_paths = bind.execute(sa.text(
        "SELECT count(*) FROM invitation WHERE "
        "pdf_path LIKE :drive OR qr_path LIKE :drive"
    ), {"drive": "_:%"}).scalar_one()
    if legacy_paths:
        print(
            f"ATTENTION: {legacy_paths} invitation(s) conservent un chemin local absolu. "
            "Aucune URL persistante n'a été inventée; régénérez-les vers Cloudinary."
        )


def upgrade():
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names()) - {"alembic_version"}
    if not tables:
        _create_schema()
    else:
        _upgrade_existing_schema(bind)


def downgrade():
    raise RuntimeError(
        "Downgrade volontairement désactivé : cette migration adopte une base existante "
        "et ne doit pas supprimer les données métier."
    )
