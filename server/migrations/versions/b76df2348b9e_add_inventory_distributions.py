"""add inventory distributions

Revision ID: b76df2348b9e
Revises: a23ce6d68a5b
Create Date: 2026-08-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b76df2348b9e"
down_revision = "a23ce6d68a5b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_distributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("distributed_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beneficiary_id"], ["beneficiaries.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("inventory_distributions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_inventory_distributions_beneficiary_id"), ["beneficiary_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_inventory_distributions_inventory_item_id"), ["inventory_item_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("inventory_distributions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_inventory_distributions_inventory_item_id"))
        batch_op.drop_index(batch_op.f("ix_inventory_distributions_beneficiary_id"))
    op.drop_table("inventory_distributions")
