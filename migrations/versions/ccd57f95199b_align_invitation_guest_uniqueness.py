"""align invitation guest uniqueness

Revision ID: ccd57f95199b
Revises: 28d6db2cbd97
Create Date: 2026-09-16 23:50:18.080014

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'ccd57f95199b'
down_revision = '28d6db2cbd97'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    constraints = inspector.get_unique_constraints("invitation")
    if any(item.get("column_names") == ["guest_id"] for item in constraints):
        return

    indexes = inspector.get_indexes("invitation")
    guest_indexes = [
        item for item in indexes
        if item.get("unique") and item.get("column_names") == ["guest_id"]
    ]

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("invitation", recreate="always") as batch_op:
            for index in guest_indexes:
                batch_op.drop_index(index["name"])
            batch_op.create_unique_constraint("uq_invitation_guest", ["guest_id"])
    else:
        for index in guest_indexes:
            op.drop_index(index["name"], table_name="invitation")
        op.create_unique_constraint("uq_invitation_guest", "invitation", ["guest_id"])


def downgrade():
    raise RuntimeError(
        "Downgrade désactivé : conserver l'unicité de invitation.guest_id protège les données."
    )
