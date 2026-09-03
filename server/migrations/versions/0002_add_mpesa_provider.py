"""Add 'mpesa' to payment_provider enum

The frontend's primary donation flow is Safaricom M-Pesa STK Push, so the
API needs to accept it as a payment_provider value alongside stripe/paypal.

Revision ID: 0002_add_mpesa
Revises: 0001_initial
Create Date: 2026-09-01
"""

from alembic import op

revision = "0002_add_mpesa"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in
    # Postgres, so autocommit is required here.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_provider ADD VALUE IF NOT EXISTS 'mpesa'")


def downgrade():
    # Postgres does not support removing a value from an enum type directly.
    # Rebuilding the type would require rewriting every dependent column;
    # left as a no-op since donations/payment_methods may already reference
    # 'mpesa' rows by the time anyone downgrades.
    pass
