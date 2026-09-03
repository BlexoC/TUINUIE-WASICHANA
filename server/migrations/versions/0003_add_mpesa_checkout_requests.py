"""Create the M-Pesa STK checkout request ledger.

Revision ID: 0003_mpesa_checkout_requests
Revises: 0002_add_mpesa
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_mpesa_checkout_requests"
down_revision = "0002_add_mpesa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mpesa_checkout_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("checkout_request_id", sa.String(64), nullable=False),
        sa.Column("merchant_request_id", sa.String(64), nullable=True),
        sa.Column("donor_id", sa.BigInteger, sa.ForeignKey("donors.id"), nullable=False),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id"), nullable=False),
        sa.Column(
            "project_id",
            sa.BigInteger,
            sa.ForeignKey("charity_projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone_number", sa.String(15), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("mpesa_receipt_number", sa.String(30), nullable=True),
        sa.Column("result_code", sa.Integer, nullable=True),
        sa.Column("result_desc", sa.String(255), nullable=True),
        sa.Column(
            "donation_id",
            sa.BigInteger,
            sa.ForeignKey("donations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("checkout_request_id", name="uq_mpesa_checkout_request_id"),
    )
    op.create_index(
        "ix_mpesa_checkout_requests_checkout_request_id",
        "mpesa_checkout_requests",
        ["checkout_request_id"],
    )


def downgrade():
    op.drop_index("ix_mpesa_checkout_requests_checkout_request_id", table_name="mpesa_checkout_requests")
    op.drop_table("mpesa_checkout_requests")
