"""Add invitation templates and associate every event.

Revision ID: 7d3f4b2a91c8
Revises: ccd57f95199b
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa


revision = "7d3f4b2a91c8"
down_revision = "ccd57f95199b"
branch_labels = None
depends_on = None


DEFAULT_TEMPLATE = {
    "slug": "template_001",
    "name": "Wedding Premium 4 pages",
    "preview_image": "templates/template_001/page_1.png",
    "primary_color": "#1f2937",
    "secondary_color": "#f8f5f0",
    "accent_color": "#c9a227",
    "heading_font": "Playfair Display",
    "body_font": "Inter",
    "is_active": True,
}


def upgrade():
    op.create_table(
        "template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("preview_image", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=False),
        sa.Column("secondary_color", sa.String(length=20), nullable=False),
        sa.Column("accent_color", sa.String(length=20), nullable=False),
        sa.Column("heading_font", sa.String(length=100), nullable=False),
        sa.Column("body_font", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_template_slug"),
    )

    bind = op.get_bind()
    template_table = sa.table(
        "template",
        sa.column("id", sa.Integer()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("preview_image", sa.String()),
        sa.column("primary_color", sa.String()),
        sa.column("secondary_color", sa.String()),
        sa.column("accent_color", sa.String()),
        sa.column("heading_font", sa.String()),
        sa.column("body_font", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    template_id = bind.execute(
        sa.select(template_table.c.id).where(
            template_table.c.slug == DEFAULT_TEMPLATE["slug"]
        )
    ).scalar_one_or_none()
    if template_id is None:
        bind.execute(template_table.insert().values(**DEFAULT_TEMPLATE))
        template_id = bind.execute(
            sa.select(template_table.c.id).where(
                template_table.c.slug == DEFAULT_TEMPLATE["slug"]
            )
        ).scalar_one()

    op.add_column("event", sa.Column("template_id", sa.Integer(), nullable=True))
    bind.execute(
        sa.text("UPDATE event SET template_id = :template_id WHERE template_id IS NULL"),
        {"template_id": template_id},
    )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("event", recreate="always") as batch_op:
            batch_op.alter_column(
                "template_id", existing_type=sa.Integer(), nullable=False
            )
            batch_op.create_foreign_key(
                "fk_event_template_id_template",
                "template",
                ["template_id"],
                ["id"],
            )
    else:
        op.alter_column(
            "event", "template_id", existing_type=sa.Integer(), nullable=False
        )
        op.create_foreign_key(
            "fk_event_template_id_template",
            "event",
            "template",
            ["template_id"],
            ["id"],
        )


def downgrade():
    raise RuntimeError(
        "Downgrade désactivé : supprimer les templates dissocierait les événements."
    )
