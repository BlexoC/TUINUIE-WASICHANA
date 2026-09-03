"""
models.py — Flask-SQLAlchemy models for the Recurring Charity Donation Platform

Mirrors schema.sql exactly: same tables, columns, enums, constraints,
and relationships. Import `db` from your Flask app factory as usual.

    from app import db
    from models import User, Donor, Charity, ...

Requires: Flask-SQLAlchemy, psycopg2-binary
"""

from datetime import date, time
from sqlalchemy import (
    CheckConstraint, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

# db is initialised in server/__init__.py and injected via init_app().
# Import it here to keep models self-contained and importable everywhere.
from server import db

# ------------------------------------------------------------
# ENUM TYPES (mirrors the PostgreSQL ENUM TYPEs in schema.sql)
# ------------------------------------------------------------
user_role_enum = PG_ENUM(
    "donor", "charity", "admin",
    name="user_role", create_type=False
)
application_status_enum = PG_ENUM(
    "pending", "approved", "rejected",
    name="application_status", create_type=False
)
charity_status_enum = PG_ENUM(
    "active", "suspended",
    name="charity_status", create_type=False
)
plan_status_enum = PG_ENUM(
    "active", "paused", "cancelled",
    name="plan_status", create_type=False
)
plan_frequency_enum = PG_ENUM(
    "weekly", "monthly", "quarterly", "yearly",
    name="plan_frequency", create_type=False
)
donation_type_enum = PG_ENUM(
    "one_time", "recurring",
    name="donation_type", create_type=False
)
payment_status_enum = PG_ENUM(
    "pending", "completed", "failed", "refunded",
    name="payment_status", create_type=False
)
payment_provider_enum = PG_ENUM(
    "stripe", "paypal",
    name="payment_provider", create_type=False
)
project_status_enum = PG_ENUM(
    "active", "completed", "archived",
    name="project_status", create_type=False
)
document_type_enum = PG_ENUM(
    "registration_certificate", "financial_audit", "director_id", "other",
    name="document_type", create_type=False
)
notification_type_enum = PG_ENUM(
    "account_created", "donation_successful", "upcoming_payment",
    "application_approved", "application_rejected", "plan_payment_failed",
    name="notification_type", create_type=False
)

# Note: create_type=False on every enum above because schema.sql already
# runs `CREATE TYPE ...` explicitly. If you'd rather let SQLAlchemy create
# the enum types itself (e.g. you're using `db.create_all()` instead of
# running schema.sql), drop create_type=False on each one.


# ------------------------------------------------------------
# CORE IDENTITY
# ------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(user_role_enum, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # 1:1 role profiles
    donor = db.relationship("Donor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    administrator = db.relationship("Administrator", back_populates="user", uselist=False, cascade="all, delete-orphan")
    charity = db.relationship("Charity", back_populates="user", uselist=False, cascade="all, delete-orphan")
    charity_applications = db.relationship("CharityApplication", back_populates="applicant", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_role", "role"),
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ------------------------------------------------------------
# DONOR PROFILE
# ------------------------------------------------------------
class Donor(db.Model):
    __tablename__ = "donors"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    default_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    user = db.relationship("User", back_populates="donor")
    payment_methods = db.relationship("PaymentMethod", back_populates="donor", cascade="all, delete-orphan")
    recurring_plans = db.relationship("RecurringDonationPlan", back_populates="donor", cascade="all, delete-orphan")
    donations = db.relationship("Donation", back_populates="donor")
    reminder = db.relationship("DonationReminder", back_populates="donor", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Donor user_id={self.user_id}>"


# ------------------------------------------------------------
# ADMINISTRATOR PROFILE
# ------------------------------------------------------------
class Administrator(db.Model):
    __tablename__ = "administrators"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    user = db.relationship("User", back_populates="administrator")
    reviewed_applications = db.relationship("CharityApplication", back_populates="reviewer")

    def __repr__(self):
        return f"<Administrator user_id={self.user_id}>"


# ------------------------------------------------------------
# CHARITY APPLICATION -> APPROVAL WORKFLOW
# ------------------------------------------------------------
class CharityApplication(db.Model):
    __tablename__ = "charity_applications"

    id = db.Column(db.BigInteger, primary_key=True)
    applicant_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    mission_statement = db.Column(db.Text)
    registration_number = db.Column(db.String(100))
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    status = db.Column(application_status_enum, nullable=False, default="pending")
    reviewed_by = db.Column(db.BigInteger, db.ForeignKey("administrators.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    rejection_reason = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    applicant = db.relationship("User", back_populates="charity_applications")
    reviewer = db.relationship("Administrator", back_populates="reviewed_applications")
    charity = db.relationship("Charity", back_populates="application", uselist=False)
    documents = db.relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_charity_applications_status", "status"),
    )

    def __repr__(self):
        return f"<CharityApplication {self.organization_name} ({self.status})>"


# ------------------------------------------------------------
# CHARITY APPLICATION VERIFICATION DOCUMENTS
# ------------------------------------------------------------
class ApplicationDocument(db.Model):
    __tablename__ = "application_documents"

    id = db.Column(db.BigInteger, primary_key=True)
    application_id = db.Column(db.BigInteger, db.ForeignKey("charity_applications.id", ondelete="CASCADE"), nullable=False)
    document_type = db.Column(document_type_enum, nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100))
    file_size_bytes = db.Column(db.BigInteger)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    application = db.relationship("CharityApplication", back_populates="documents")

    __table_args__ = (
        Index("idx_application_documents_application", "application_id"),
    )

    def __repr__(self):
        return f"<ApplicationDocument {self.file_name} ({self.document_type})>"


# ------------------------------------------------------------
# LIVE CHARITIES
# ------------------------------------------------------------
class Charity(db.Model):
    __tablename__ = "charities"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    application_id = db.Column(db.BigInteger, db.ForeignKey("charity_applications.id", ondelete="SET NULL"), unique=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    mission_statement = db.Column(db.Text)
    logo_url = db.Column(db.String(500))
    website_url = db.Column(db.String(500))
    registration_number = db.Column(db.String(100))
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    status = db.Column(charity_status_enum, nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = db.relationship("User", back_populates="charity")
    application = db.relationship("CharityApplication", back_populates="charity")
    projects = db.relationship("CharityProject", back_populates="charity", cascade="all, delete-orphan")
    recurring_plans = db.relationship("RecurringDonationPlan", back_populates="charity")
    donations = db.relationship("Donation", back_populates="charity")
    beneficiaries = db.relationship("Beneficiary", back_populates="charity", cascade="all, delete-orphan")
    inventory_items = db.relationship("InventoryItem", back_populates="charity", cascade="all, delete-orphan")
    stories = db.relationship("Story", back_populates="charity", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_charities_status", "status"),
    )

    @property
    def total_received(self):
        """Sum of completed donations. Prefer querying the charity_totals
        view for bulk/list use — this property is convenient for a single
        charity's detail page."""
        total = db.session.query(func.coalesce(func.sum(Donation.amount), 0)).filter(
            Donation.charity_id == self.id,
            Donation.payment_status == "completed"
        ).scalar()
        return total

    def __repr__(self):
        return f"<Charity {self.name}>"


# ------------------------------------------------------------
# CHARITY PROJECTS / CAMPAIGNS
# (a fundable initiative within a charity — e.g. "Emergency Dignity Kits
# Distribution" — with its own goal and progress, shown on the charity's
# "Active Projects" page)
# ------------------------------------------------------------
class CharityProject(db.Model):
    __tablename__ = "charity_projects"

    id = db.Column(db.BigInteger, primary_key=True)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    image_url = db.Column(db.String(500))
    goal_amount = db.Column(db.Numeric(10, 2), nullable=False)
    is_urgent = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(project_status_enum, nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    charity = db.relationship("Charity", back_populates="projects")
    donations = db.relationship("Donation", back_populates="project")
    recurring_plans = db.relationship("RecurringDonationPlan", back_populates="project")

    __table_args__ = (
        CheckConstraint("goal_amount > 0", name="ck_project_goal_positive"),
        Index("idx_projects_charity", "charity_id"),
        Index("idx_projects_status", "status"),
    )

    @property
    def amount_raised(self):
        total = db.session.query(func.coalesce(func.sum(Donation.amount), 0)).filter(
            Donation.project_id == self.id,
            Donation.payment_status == "completed"
        ).scalar()
        return total

    @property
    def percent_funded(self):
        raised = self.amount_raised
        if not self.goal_amount:
            return 0
        return round(float(raised) / float(self.goal_amount) * 100, 1)

    def __repr__(self):
        return f"<CharityProject {self.title} ({self.status})>"


# ------------------------------------------------------------
# SAVED PAYMENT METHODS
# ------------------------------------------------------------
class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"

    id = db.Column(db.BigInteger, primary_key=True)
    donor_id = db.Column(db.BigInteger, db.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False)
    provider = db.Column(payment_provider_enum, nullable=False)
    provider_customer_id = db.Column(db.String(255), nullable=False)
    provider_payment_method_id = db.Column(db.String(255), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    donor = db.relationship("Donor", back_populates="payment_methods")
    recurring_plans = db.relationship("RecurringDonationPlan", back_populates="payment_method")

    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_method_id", name="uq_payment_methods_provider_pmid"),
        Index("idx_payment_methods_donor", "donor_id"),
    )

    def __repr__(self):
        return f"<PaymentMethod {self.provider} donor_id={self.donor_id}>"


# ------------------------------------------------------------
# RECURRING DONATION PLANS
# ------------------------------------------------------------
class RecurringDonationPlan(db.Model):
    __tablename__ = "recurring_donation_plans"

    id = db.Column(db.BigInteger, primary_key=True)
    donor_id = db.Column(db.BigInteger, db.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.BigInteger, db.ForeignKey("charity_projects.id", ondelete="SET NULL"))
    payment_method_id = db.Column(db.BigInteger, db.ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.CHAR(3), nullable=False, default="USD")
    frequency = db.Column(plan_frequency_enum, nullable=False, default="monthly")
    day_of_month = db.Column(db.SmallInteger)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    next_donation_date = db.Column(db.Date, nullable=False)
    status = db.Column(plan_status_enum, nullable=False, default="active")
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    donor = db.relationship("Donor", back_populates="recurring_plans")
    charity = db.relationship("Charity", back_populates="recurring_plans")
    project = db.relationship("CharityProject", back_populates="recurring_plans")
    payment_method = db.relationship("PaymentMethod", back_populates="recurring_plans")
    donations = db.relationship("Donation", back_populates="recurring_plan")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_plan_amount_positive"),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_plan_day_of_month"),
        Index("idx_plans_donor", "donor_id"),
        Index("idx_plans_charity", "charity_id"),
        Index("idx_plans_next_run", "next_donation_date", postgresql_where=(status == "active")),
    )

    def __repr__(self):
        return f"<RecurringDonationPlan {self.amount} {self.currency} {self.frequency} donor_id={self.donor_id}>"


# ------------------------------------------------------------
# DONATIONS
# ------------------------------------------------------------
class Donation(db.Model):
    __tablename__ = "donations"

    id = db.Column(db.BigInteger, primary_key=True)
    donor_id = db.Column(db.BigInteger, db.ForeignKey("donors.id", ondelete="RESTRICT"), nullable=False)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="RESTRICT"), nullable=False)
    project_id = db.Column(db.BigInteger, db.ForeignKey("charity_projects.id", ondelete="SET NULL"))
    recurring_plan_id = db.Column(db.BigInteger, db.ForeignKey("recurring_donation_plans.id", ondelete="SET NULL"))
    donation_type = db.Column(donation_type_enum, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.CHAR(3), nullable=False, default="USD")
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    payment_provider = db.Column(payment_provider_enum, nullable=False)
    provider_transaction_id = db.Column(db.String(255), nullable=False)
    payment_status = db.Column(payment_status_enum, nullable=False, default="pending")
    donated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    donor = db.relationship("Donor", back_populates="donations")
    charity = db.relationship("Charity", back_populates="donations")
    project = db.relationship("CharityProject", back_populates="donations")
    recurring_plan = db.relationship("RecurringDonationPlan", back_populates="donations")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_donation_amount_positive"),
        UniqueConstraint("payment_provider", "provider_transaction_id", name="uq_donations_provider_txn"),
        Index("idx_donations_donor", "donor_id"),
        Index("idx_donations_charity", "charity_id"),
        Index("idx_donations_project", "project_id"),
        Index("idx_donations_plan", "recurring_plan_id"),
        Index("idx_donations_status", "payment_status"),
    )

    def to_dict(self, viewer_role="donor"):
        """Serialize respecting anonymity: charities should never see a
        donor's identity on an anonymous donation. Admin/donor views can
        pass viewer_role='admin' or 'self' to bypass the mask."""
        base = {
            "id": self.id,
            "charity_id": self.charity_id,
            "amount": str(self.amount),
            "currency": self.currency,
            "donation_type": self.donation_type,
            "payment_status": self.payment_status,
            "donated_at": self.donated_at.isoformat() if self.donated_at else None,
        }
        if self.is_anonymous and viewer_role == "charity":
            base["donor"] = None
        else:
            base["donor_id"] = self.donor_id
        return base

    def __repr__(self):
        return f"<Donation {self.amount} {self.currency} -> charity_id={self.charity_id}>"


# ------------------------------------------------------------
# BENEFICIARIES
# ------------------------------------------------------------
class Beneficiary(db.Model):
    __tablename__ = "beneficiaries"

    id = db.Column(db.BigInteger, primary_key=True)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    age = db.Column(db.SmallInteger)
    gender = db.Column(db.String(30))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    charity = db.relationship("Charity", back_populates="beneficiaries")
    distributions = db.relationship("InventoryDistribution", back_populates="beneficiary", cascade="all, delete-orphan")
    stories = db.relationship("Story", back_populates="beneficiary")

    __table_args__ = (
        Index("idx_beneficiaries_charity", "charity_id"),
    )

    def __repr__(self):
        return f"<Beneficiary {self.full_name}>"


# ------------------------------------------------------------
# INVENTORY
# ------------------------------------------------------------
class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.BigInteger, primary_key=True)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    unit = db.Column(db.String(50))
    quantity_available = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    charity = db.relationship("Charity", back_populates="inventory_items")
    distributions = db.relationship("InventoryDistribution", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("quantity_available >= 0", name="ck_inventory_qty_nonneg"),
        Index("idx_inventory_charity", "charity_id"),
    )

    def __repr__(self):
        return f"<InventoryItem {self.item_name} qty={self.quantity_available}>"


class InventoryDistribution(db.Model):
    __tablename__ = "inventory_distributions"

    id = db.Column(db.BigInteger, primary_key=True)
    inventory_item_id = db.Column(db.BigInteger, db.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    beneficiary_id = db.Column(db.BigInteger, db.ForeignKey("beneficiaries.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    distributed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = db.Column(db.Text)

    item = db.relationship("InventoryItem", back_populates="distributions")
    beneficiary = db.relationship("Beneficiary", back_populates="distributions")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_distribution_qty_positive"),
        Index("idx_distributions_item", "inventory_item_id"),
        Index("idx_distributions_beneficiary", "beneficiary_id"),
    )

    def __repr__(self):
        return f"<InventoryDistribution item_id={self.inventory_item_id} qty={self.quantity}>"


# ------------------------------------------------------------
# BENEFICIARY IMPACT STORIES
# ------------------------------------------------------------
class Story(db.Model):
    __tablename__ = "stories"

    id = db.Column(db.BigInteger, primary_key=True)
    charity_id = db.Column(db.BigInteger, db.ForeignKey("charities.id", ondelete="CASCADE"), nullable=False)
    beneficiary_id = db.Column(db.BigInteger, db.ForeignKey("beneficiaries.id", ondelete="SET NULL"))
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    charity = db.relationship("Charity", back_populates="stories")
    beneficiary = db.relationship("Beneficiary", back_populates="stories")

    __table_args__ = (
        Index("idx_stories_charity", "charity_id"),
    )

    def __repr__(self):
        return f"<Story {self.title}>"


# ------------------------------------------------------------
# DONOR MONTHLY REMINDER PREFERENCE
# ------------------------------------------------------------
class DonationReminder(db.Model):
    __tablename__ = "donation_reminders"

    id = db.Column(db.BigInteger, primary_key=True)
    donor_id = db.Column(db.BigInteger, db.ForeignKey("donors.id", ondelete="CASCADE"), nullable=False, unique=True)
    day_of_month = db.Column(db.SmallInteger, nullable=False)
    time_of_day = db.Column(db.Time, nullable=False, default=time(9, 0))
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    donor = db.relationship("Donor", back_populates="reminder")

    __table_args__ = (
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_reminder_day_of_month"),
    )

    def __repr__(self):
        return f"<DonationReminder donor_id={self.donor_id} day={self.day_of_month}>"

"""

Tracks every STK Push request from initiation through to the async callback.

Why this table exists: Daraja's callback payload does NOT echo back the
AccountReference, charity_id, donor_id, or anything else custom you sent in
the original stkpush request — it only returns Amount, MpesaReceiptNumber,
PhoneNumber, and TransactionDate. So the callback handler has no reliable
way to know which donor/charity a payment was for unless we recorded that
ourselves at the moment we initiated the push. CheckoutRequestID is the one
value Daraja guarantees to echo back, so it's the join key.

Adjust the ForeignKey table names below ("donors.id", "charities.id",
"projects.id", "donations.id") if your actual __tablename__ values differ —
these are guesses based on your route file's imports (Donor, Charity,
Project, Donation). Add this import to wherever your other models are
aggregated (e.g. server/models/__init__.py) so Flask-Migrate/SQLAlchemy
picks it up.
"""



class MpesaCheckoutRequest(db.Model):
    __tablename__ = "mpesa_checkout_requests"

    id = db.Column(db.Integer, primary_key=True)

    # The one value Daraja reliably echoes back in the callback — our join key.
    checkout_request_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    merchant_request_id = db.Column(db.String(64), nullable=True)

    donor_id = db.Column(db.Integer, db.ForeignKey("donors.id"), nullable=False)
    charity_id = db.Column(db.Integer, db.ForeignKey("charities.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)

    phone_number = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Integer, nullable=False)

    # pending -> completed | failed, set by the callback (or by a fallback
    # query if the callback is delayed/missed)
    status = db.Column(db.String(20), nullable=False, default="pending")
    mpesa_receipt_number = db.Column(db.String(30), nullable=True)
    result_code = db.Column(db.Integer, nullable=True)
    result_desc = db.Column(db.String(255), nullable=True)

    # Set once we've created the actual Donation row, so we never double-record
    # the same receipt if Daraja retries the callback.
    donation_id = db.Column(db.Integer, db.ForeignKey("donations.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    donor = db.relationship("Donor")
    charity = db.relationship("Charity")
    donation = db.relationship("Donation")


# ------------------------------------------------------------
# IN-APP NOTIFICATIONS
# (drives the Notifications page: account events, donation
# confirmations, upcoming recurring-payment reminders, application
# status updates)
# ------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = db.Column(notification_type_enum, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    related_entity_type = db.Column(db.String(50))
    related_entity_id = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    user = db.relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_notifications_user", "user_id"),
        Index("idx_notifications_unread", "user_id", postgresql_where=(is_read == False)),  # noqa: E712
    )

    def __repr__(self):
        return f"<Notification {self.type} user_id={self.user_id} read={self.is_read}>"