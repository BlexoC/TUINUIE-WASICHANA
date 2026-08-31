"""Initial schema — all tables, enums, indexes, views

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── ENUM TYPES ───────────────────────────────────────────────────────
    user_role = postgresql.ENUM(
        "donor", "charity", "admin", name="user_role", create_type=False
    )
    application_status = postgresql.ENUM(
        "pending", "approved", "rejected", name="application_status", create_type=False
    )
    charity_status = postgresql.ENUM(
        "active", "suspended", name="charity_status", create_type=False
    )
    plan_status = postgresql.ENUM(
        "active", "paused", "cancelled", name="plan_status", create_type=False
    )
    plan_frequency = postgresql.ENUM(
        "weekly", "monthly", "quarterly", "yearly", name="plan_frequency", create_type=False
    )
    donation_type = postgresql.ENUM(
        "one_time", "recurring", name="donation_type", create_type=False
    )
    payment_status = postgresql.ENUM(
        "pending", "completed", "failed", "refunded", name="payment_status", create_type=False
    )
    payment_provider = postgresql.ENUM(
        "stripe", "paypal", name="payment_provider", create_type=False
    )
    project_status = postgresql.ENUM(
        "active", "completed", "archived", name="project_status", create_type=False
    )
    document_type = postgresql.ENUM(
        "registration_certificate", "financial_audit", "director_id", "other",
        name="document_type", create_type=False
    )
    notification_type = postgresql.ENUM(
        "account_created", "donation_successful", "upcoming_payment",
        "application_approved", "application_rejected", "plan_payment_failed",
        name="notification_type", create_type=False
    )

    bind = op.get_bind()

    for enum in [
        user_role, application_status, charity_status, plan_status,
        plan_frequency, donation_type, payment_status, payment_provider,
        project_status, document_type, notification_type,
    ]:
        enum.create(op.get_bind(), checkfirst=True)

    # ── USERS ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("phone", sa.String(30)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_users_role", "users", ["role"])

    # ── DONORS ───────────────────────────────────────────────────────────
    op.create_table(
        "donors",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("default_anonymous", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── ADMINISTRATORS ────────────────────────────────────────────────────
    op.create_table(
        "administrators",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── CHARITY APPLICATIONS ──────────────────────────────────────────────
    op.create_table(
        "charity_applications",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("applicant_user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("mission_statement", sa.Text),
        sa.Column("registration_number", sa.String(100)),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(30)),
        sa.Column("address", sa.Text),
        sa.Column("status", application_status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.BigInteger, sa.ForeignKey("administrators.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_charity_applications_status", "charity_applications", ["status"])

    # ── APPLICATION DOCUMENTS ─────────────────────────────────────────────
    op.create_table(
        "application_documents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("application_id", sa.BigInteger, sa.ForeignKey("charity_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_application_documents_application", "application_documents", ["application_id"])

    # ── CHARITIES ─────────────────────────────────────────────────────────
    op.create_table(
        "charities",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("application_id", sa.BigInteger, sa.ForeignKey("charity_applications.id", ondelete="SET NULL"), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("mission_statement", sa.Text),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("website_url", sa.String(500)),
        sa.Column("registration_number", sa.String(100)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(30)),
        sa.Column("address", sa.Text),
        sa.Column("status", charity_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_charities_status", "charities", ["status"])

    # ── CHARITY PROJECTS ──────────────────────────────────────────────────
    op.create_table(
        "charity_projects",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(100)),
        sa.Column("image_url", sa.String(500)),
        sa.Column("goal_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_urgent", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("status", project_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("goal_amount > 0", name="ck_project_goal_positive"),
    )
    op.create_index("idx_projects_charity", "charity_projects", ["charity_id"])
    op.create_index("idx_projects_status", "charity_projects", ["status"])

    # ── PAYMENT METHODS ───────────────────────────────────────────────────
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("donor_id", sa.BigInteger, sa.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("provider_customer_id", sa.String(255), nullable=False),
        sa.Column("provider_payment_method_id", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_payment_method_id", name="uq_payment_methods_provider_pmid"),
    )
    op.create_index("idx_payment_methods_donor", "payment_methods", ["donor_id"])

    # ── RECURRING DONATION PLANS ──────────────────────────────────────────
    op.create_table(
        "recurring_donation_plans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("donor_id", sa.BigInteger, sa.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("charity_projects.id", ondelete="SET NULL")),
        sa.Column("payment_method_id", sa.BigInteger, sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("frequency", plan_frequency, nullable=False, server_default="monthly"),
        sa.Column("day_of_month", sa.SmallInteger),
        sa.Column("start_date", sa.Date, nullable=False, server_default=sa.func.current_date()),
        sa.Column("next_donation_date", sa.Date, nullable=False),
        sa.Column("status", plan_status, nullable=False, server_default="active"),
        sa.Column("is_anonymous", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_plan_amount_positive"),
        sa.CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_plan_day_of_month"),
    )
    op.create_index("idx_plans_donor", "recurring_donation_plans", ["donor_id"])
    op.create_index("idx_plans_charity", "recurring_donation_plans", ["charity_id"])
    # Partial index: only active plans need next-run scheduling queries
    op.execute(
        "CREATE INDEX idx_plans_next_run ON recurring_donation_plans(next_donation_date) "
        "WHERE status = 'active'"
    )

    # ── DONATIONS ─────────────────────────────────────────────────────────
    op.create_table(
        "donations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("donor_id", sa.BigInteger, sa.ForeignKey("donors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("charity_projects.id", ondelete="SET NULL")),
        sa.Column("recurring_plan_id", sa.BigInteger, sa.ForeignKey("recurring_donation_plans.id", ondelete="SET NULL")),
        sa.Column("donation_type", donation_type, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("is_anonymous", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("payment_provider", payment_provider, nullable=False),
        sa.Column("provider_transaction_id", sa.String(255), nullable=False),
        sa.Column("payment_status", payment_status, nullable=False, server_default="pending"),
        sa.Column("donated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_donation_amount_positive"),
        sa.UniqueConstraint("payment_provider", "provider_transaction_id", name="uq_donations_provider_txn"),
    )
    for idx_name, cols in [
        ("idx_donations_donor",   ["donor_id"]),
        ("idx_donations_charity", ["charity_id"]),
        ("idx_donations_project", ["project_id"]),
        ("idx_donations_plan",    ["recurring_plan_id"]),
        ("idx_donations_status",  ["payment_status"]),
    ]:
        op.create_index(idx_name, "donations", cols)

    # ── BENEFICIARIES ─────────────────────────────────────────────────────
    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("age", sa.SmallInteger),
        sa.Column("gender", sa.String(30)),
        sa.Column("location", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_beneficiaries_charity", "beneficiaries", ["charity_id"])

    # ── INVENTORY ─────────────────────────────────────────────────────────
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("unit", sa.String(50)),
        sa.Column("quantity_available", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity_available >= 0", name="ck_inventory_qty_nonneg"),
    )
    op.create_index("idx_inventory_charity", "inventory_items", ["charity_id"])

    op.create_table(
        "inventory_distributions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("inventory_item_id", sa.BigInteger, sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("beneficiary_id", sa.BigInteger, sa.ForeignKey("beneficiaries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("distributed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.Text),
        sa.CheckConstraint("quantity > 0", name="ck_distribution_qty_positive"),
    )
    op.create_index("idx_distributions_item", "inventory_distributions", ["inventory_item_id"])
    op.create_index("idx_distributions_beneficiary", "inventory_distributions", ["beneficiary_id"])

    # ── STORIES ───────────────────────────────────────────────────────────
    op.create_table(
        "stories",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("charity_id", sa.BigInteger, sa.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("beneficiary_id", sa.BigInteger, sa.ForeignKey("beneficiaries.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("image_url", sa.String(500)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_stories_charity", "stories", ["charity_id"])

    # ── DONATION REMINDERS ────────────────────────────────────────────────
    op.create_table(
        "donation_reminders",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("donor_id", sa.BigInteger, sa.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("day_of_month", sa.SmallInteger, nullable=False),
        sa.Column("time_of_day", sa.Time, nullable=False, server_default="09:00"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="TRUE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_reminder_day_of_month"),
    )

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("related_entity_type", sa.String(50)),
        sa.Column("related_entity_id", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_notifications_user", "notifications", ["user_id"])
    op.execute(
        "CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE is_read = FALSE"
    )

    # ── HELPER VIEWS ──────────────────────────────────────────────────────
    op.execute("""
        CREATE VIEW charity_totals AS
        SELECT
            c.id   AS charity_id,
            c.name,
            COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0) AS total_received
        FROM charities c
        LEFT JOIN donations d ON d.charity_id = c.id
        GROUP BY c.id, c.name
    """)

    op.execute("""
        CREATE VIEW project_totals AS
        SELECT
            p.id         AS project_id,
            p.charity_id,
            p.title,
            p.goal_amount,
            COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0) AS amount_raised,
            ROUND(
                COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0)
                / NULLIF(p.goal_amount, 0) * 100, 1
            ) AS percent_funded
        FROM charity_projects p
        LEFT JOIN donations d ON d.project_id = p.id
        GROUP BY p.id, p.charity_id, p.title, p.goal_amount
    """)


def downgrade():
    op.execute("DROP VIEW IF EXISTS project_totals")
    op.execute("DROP VIEW IF EXISTS charity_totals")

    for table in [
        "notifications", "donation_reminders", "stories",
        "inventory_distributions", "inventory_items", "beneficiaries",
        "donations", "recurring_donation_plans", "payment_methods",
        "charity_projects", "charities", "application_documents",
        "charity_applications", "administrators", "donors", "users",
    ]:
        op.drop_table(table)

    for enum_name in [
        "notification_type", "document_type", "project_status",
        "payment_provider", "payment_status", "donation_type",
        "plan_frequency", "plan_status", "charity_status",
        "application_status", "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
