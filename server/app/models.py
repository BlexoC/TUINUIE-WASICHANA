"""
SQLAlchemy 2.0 model layer for the donation platform.

Covers all tables from the agreed schema:
users, donors, administrators, charity_applications, charities,
application_documents, charity_projects, payment_methods,
recurring_donation_plans, donations, beneficiaries, inventory_items,
inventory_distributions, stories, donation_reminders, notifications
(16 tables total).

Conventions used throughout:
- SQLAlchemy 2.0 typed declarative style (Mapped / mapped_column)
- Enumerated "note" fields from the schema are enforced with CHECK
  constraints AND validated in Python via @validates for fast, clear
  failures before a round trip to the database
- Cascades: tight 1-1 "profile" tables (donors, administrators,
  donation_reminders) cascade delete with their owning user; child
  records that only make sense in the context of a parent (documents,
  distributions, stories, etc.) cascade delete with that parent;
  financial/audit records (donations, payment_methods, recurring
  plans) do NOT cascade delete automatically so financial history is
  never silently destroyed when a donor row is removed
- server_default / default pairs are set so behavior is consistent
  whether rows are created by the ORM or raw SQL
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)


class Base(DeclarativeBase):
    """Shared declarative base for all models."""
    pass


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str, field_name: str = "email") -> str:
    if not value or not EMAIL_RE.match(value):
        raise ValueError(f"Invalid {field_name}: {value!r}")
    return value


def _validate_positive(value, field_name: str) -> object:
    if value is None or value <= 0:
        raise ValueError(f"{field_name} must be greater than 0, got {value!r}")
    return value


def _validate_non_negative(value, field_name: str) -> object:
    if value is None or value < 0:
        raise ValueError(f"{field_name} must be >= 0, got {value!r}")
    return value


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('donor', 'charity', 'admin')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # 1-1 profile relationships
    donor: Mapped[Optional["Donor"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    administrator: Mapped[Optional["Administrator"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )

    # 1-* relationships
    charity_applications: Mapped[list["CharityApplication"]] = relationship(
        back_populates="applicant", foreign_keys="CharityApplication.applicant_user_id"
    )
    charity: Mapped[Optional["Charity"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("email")
    def validate_email(self, key, value):
        return _validate_email(value)

    @validates("role")
    def validate_role(self, key, value):
        allowed = {"donor", "charity", "admin"}
        if value not in allowed:
            raise ValueError(f"role must be one of {allowed}, got {value!r}")
        return value

    @validates("username")
    def validate_username(self, key, value):
        if not value or not value.strip():
            raise ValueError("username must not be empty")
        return value

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# donors  (1-1 with users)
# ---------------------------------------------------------------------------
class Donor(Base):
    __tablename__ = "donors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    default_anonymous: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="donor")

    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="donor", cascade="all, delete-orphan", passive_deletes=True
    )
    recurring_donation_plans: Mapped[list["RecurringDonationPlan"]] = relationship(
        back_populates="donor"
    )
    donations: Mapped[list["Donation"]] = relationship(back_populates="donor")
    donation_reminder: Mapped[Optional["DonationReminder"]] = relationship(
        back_populates="donor", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Donor id={self.id} user_id={self.user_id}>"


# ---------------------------------------------------------------------------
# administrators  (1-1 with users)
# ---------------------------------------------------------------------------
class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="administrator")

    reviewed_applications: Mapped[list["CharityApplication"]] = relationship(
        back_populates="reviewer", foreign_keys="CharityApplication.reviewed_by"
    )

    def __repr__(self) -> str:
        return f"<Administrator id={self.id} user_id={self.user_id}>"


# ---------------------------------------------------------------------------
# charity_applications
# ---------------------------------------------------------------------------
class CharityApplication(Base):
    __tablename__ = "charity_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_charity_applications_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    mission_statement: Mapped[Optional[str]] = mapped_column(String)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100))
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30))
    address: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("administrators.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]]
    rejection_reason: Mapped[Optional[str]] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant: Mapped["User"] = relationship(
        back_populates="charity_applications", foreign_keys=[applicant_user_id]
    )
    reviewer: Mapped[Optional["Administrator"]] = relationship(
        back_populates="reviewed_applications", foreign_keys=[reviewed_by]
    )
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", passive_deletes=True
    )
    charity: Mapped[Optional["Charity"]] = relationship(
        back_populates="application", uselist=False
    )

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"pending", "approved", "rejected"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value

    @validates("contact_email")
    def validate_contact_email(self, key, value):
        return _validate_email(value, "contact_email")

    @validates("rejection_reason")
    def validate_rejection_reason(self, key, value):
        if self.status == "rejected" and not value:
            raise ValueError("rejection_reason is required when status is 'rejected'")
        return value

    def __repr__(self) -> str:
        return f"<CharityApplication id={self.id} org={self.organization_name!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# charities  (1-1 with users, 1-1 with the approving application)
# ---------------------------------------------------------------------------
class Charity(Base):
    __tablename__ = "charities"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="ck_charities_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("charity_applications.id", ondelete="SET NULL"), unique=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    mission_statement: Mapped[Optional[str]] = mapped_column(String)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    website_url: Mapped[Optional[str]] = mapped_column(String(500))
    registration_number: Mapped[Optional[str]] = mapped_column(String(100))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30))
    address: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="charity")
    application: Mapped[Optional["CharityApplication"]] = relationship(
        back_populates="charity"
    )

    projects: Mapped[list["CharityProject"]] = relationship(
        back_populates="charity", cascade="all, delete-orphan", passive_deletes=True
    )
    beneficiaries: Mapped[list["Beneficiary"]] = relationship(
        back_populates="charity", cascade="all, delete-orphan", passive_deletes=True
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="charity", cascade="all, delete-orphan", passive_deletes=True
    )
    stories: Mapped[list["Story"]] = relationship(
        back_populates="charity", cascade="all, delete-orphan", passive_deletes=True
    )
    donations: Mapped[list["Donation"]] = relationship(back_populates="charity")
    recurring_donation_plans: Mapped[list["RecurringDonationPlan"]] = relationship(
        back_populates="charity"
    )

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"active", "suspended"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value

    @validates("contact_email")
    def validate_contact_email(self, key, value):
        if value is not None:
            return _validate_email(value, "contact_email")
        return value

    def __repr__(self) -> str:
        return f"<Charity id={self.id} name={self.name!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# application_documents
# ---------------------------------------------------------------------------
class ApplicationDocument(Base):
    __tablename__ = "application_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('registration_certificate', 'financial_audit', 'director_id', 'other')",
            name="ck_application_documents_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("charity_applications.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]]
    uploaded_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    application: Mapped["CharityApplication"] = relationship(back_populates="documents")

    @validates("document_type")
    def validate_document_type(self, key, value):
        allowed = {"registration_certificate", "financial_audit", "director_id", "other"}
        if value not in allowed:
            raise ValueError(f"document_type must be one of {allowed}, got {value!r}")
        return value

    @validates("file_size_bytes")
    def validate_file_size_bytes(self, key, value):
        if value is not None and value < 0:
            raise ValueError("file_size_bytes must be >= 0")
        return value

    def __repr__(self) -> str:
        return f"<ApplicationDocument id={self.id} type={self.document_type!r}>"


# ---------------------------------------------------------------------------
# charity_projects
# ---------------------------------------------------------------------------
class CharityProject(Base):
    __tablename__ = "charity_projects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'archived')", name="ck_charity_projects_status"),
        CheckConstraint("goal_amount > 0", name="ck_charity_projects_goal_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    goal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_urgent: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    charity: Mapped["Charity"] = relationship(back_populates="projects")
    donations: Mapped[list["Donation"]] = relationship(back_populates="project")
    recurring_donation_plans: Mapped[list["RecurringDonationPlan"]] = relationship(
        back_populates="project"
    )

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"active", "completed", "archived"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value

    @validates("goal_amount")
    def validate_goal_amount(self, key, value):
        return _validate_positive(value, "goal_amount")

    def __repr__(self) -> str:
        return f"<CharityProject id={self.id} title={self.title!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# payment_methods
# ---------------------------------------------------------------------------
class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    __table_args__ = (
        CheckConstraint("provider IN ('stripe', 'paypal')", name="ck_payment_methods_provider"),
        UniqueConstraint(
            "provider", "provider_payment_method_id", name="uq_payment_methods_provider_pm_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_payment_method_id: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    donor: Mapped["Donor"] = relationship(back_populates="payment_methods")
    recurring_donation_plans: Mapped[list["RecurringDonationPlan"]] = relationship(
        back_populates="payment_method"
    )

    @validates("provider")
    def validate_provider(self, key, value):
        allowed = {"stripe", "paypal"}
        if value not in allowed:
            raise ValueError(f"provider must be one of {allowed}, got {value!r}")
        return value

    def __repr__(self) -> str:
        return f"<PaymentMethod id={self.id} provider={self.provider!r}>"


# ---------------------------------------------------------------------------
# recurring_donation_plans
# ---------------------------------------------------------------------------
class RecurringDonationPlan(Base):
    __tablename__ = "recurring_donation_plans"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name="ck_recurring_plans_frequency",
        ),
        CheckConstraint("status IN ('active', 'paused', 'cancelled')", name="ck_recurring_plans_status"),
        CheckConstraint("amount > 0", name="ck_recurring_plans_amount_positive"),
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month BETWEEN 1 AND 31)",
            name="ck_recurring_plans_day_of_month_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="CASCADE"), nullable=False
    )
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("charity_projects.id", ondelete="SET NULL")
    )
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly", server_default="monthly"
    )
    day_of_month: Mapped[Optional[int]]
    start_date: Mapped[date] = mapped_column(nullable=False)
    next_donation_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    is_anonymous: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    donor: Mapped["Donor"] = relationship(back_populates="recurring_donation_plans")
    charity: Mapped["Charity"] = relationship(back_populates="recurring_donation_plans")
    project: Mapped[Optional["CharityProject"]] = relationship(
        back_populates="recurring_donation_plans"
    )
    payment_method: Mapped["PaymentMethod"] = relationship(
        back_populates="recurring_donation_plans"
    )
    donations: Mapped[list["Donation"]] = relationship(back_populates="recurring_plan")

    @validates("frequency")
    def validate_frequency(self, key, value):
        allowed = {"weekly", "monthly", "quarterly", "yearly"}
        if value not in allowed:
            raise ValueError(f"frequency must be one of {allowed}, got {value!r}")
        return value

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"active", "paused", "cancelled"}
        if value not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {value!r}")
        return value

    @validates("amount")
    def validate_amount(self, key, value):
        return _validate_positive(value, "amount")

    @validates("day_of_month")
    def validate_day_of_month(self, key, value):
        if value is not None and not (1 <= value <= 31):
            raise ValueError("day_of_month must be between 1 and 31")
        return value

    @validates("currency")
    def validate_currency(self, key, value):
        if not value or len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a 3-letter ISO code")
        return value.upper()

    def __repr__(self) -> str:
        return f"<RecurringDonationPlan id={self.id} amount={self.amount} frequency={self.frequency!r}>"


# ---------------------------------------------------------------------------
# donations
# ---------------------------------------------------------------------------
class Donation(Base):
    __tablename__ = "donations"
    __table_args__ = (
        CheckConstraint(
            "donation_type IN ('one_time', 'recurring')", name="ck_donations_type"
        ),
        CheckConstraint(
            "payment_provider IN ('stripe', 'paypal')", name="ck_donations_provider"
        ),
        CheckConstraint(
            "payment_status IN ('pending', 'completed', 'failed', 'refunded')",
            name="ck_donations_payment_status",
        ),
        CheckConstraint("amount > 0", name="ck_donations_amount_positive"),
        UniqueConstraint(
            "payment_provider", "provider_transaction_id", name="uq_donations_provider_txn_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="RESTRICT"), nullable=False
    )
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("charity_projects.id", ondelete="SET NULL")
    )
    recurring_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recurring_donation_plans.id", ondelete="SET NULL")
    )
    donation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    is_anonymous: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    payment_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    donated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    donor: Mapped["Donor"] = relationship(back_populates="donations")
    charity: Mapped["Charity"] = relationship(back_populates="donations")
    project: Mapped[Optional["CharityProject"]] = relationship(back_populates="donations")
    recurring_plan: Mapped[Optional["RecurringDonationPlan"]] = relationship(
        back_populates="donations"
    )

    @validates("donation_type")
    def validate_donation_type(self, key, value):
        allowed = {"one_time", "recurring"}
        if value not in allowed:
            raise ValueError(f"donation_type must be one of {allowed}, got {value!r}")
        return value

    @validates("payment_provider")
    def validate_payment_provider(self, key, value):
        allowed = {"stripe", "paypal"}
        if value not in allowed:
            raise ValueError(f"payment_provider must be one of {allowed}, got {value!r}")
        return value

    @validates("payment_status")
    def validate_payment_status(self, key, value):
        allowed = {"pending", "completed", "failed", "refunded"}
        if value not in allowed:
            raise ValueError(f"payment_status must be one of {allowed}, got {value!r}")
        return value

    @validates("amount")
    def validate_amount(self, key, value):
        return _validate_positive(value, "amount")

    @validates("currency")
    def validate_currency(self, key, value):
        if not value or len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a 3-letter ISO code")
        return value.upper()

    def __repr__(self) -> str:
        return f"<Donation id={self.id} amount={self.amount} status={self.payment_status!r}>"


# ---------------------------------------------------------------------------
# beneficiaries
# ---------------------------------------------------------------------------
class Beneficiary(Base):
    __tablename__ = "beneficiaries"
    __table_args__ = (
        CheckConstraint("age IS NULL OR age >= 0", name="ck_beneficiaries_age_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]]
    gender: Mapped[Optional[str]] = mapped_column(String(30))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    charity: Mapped["Charity"] = relationship(back_populates="beneficiaries")
    distributions: Mapped[list["InventoryDistribution"]] = relationship(
        back_populates="beneficiary", cascade="all, delete-orphan", passive_deletes=True
    )
    stories: Mapped[list["Story"]] = relationship(back_populates="beneficiary")

    @validates("age")
    def validate_age(self, key, value):
        if value is not None and value < 0:
            raise ValueError("age must be >= 0")
        return value

    @validates("full_name")
    def validate_full_name(self, key, value):
        if not value or not value.strip():
            raise ValueError("full_name must not be empty")
        return value

    def __repr__(self) -> str:
        return f"<Beneficiary id={self.id} name={self.full_name!r}>"


# ---------------------------------------------------------------------------
# inventory_items
# ---------------------------------------------------------------------------
class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("quantity_available >= 0", name="ck_inventory_items_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="CASCADE"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    quantity_available: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    charity: Mapped["Charity"] = relationship(back_populates="inventory_items")
    distributions: Mapped[list["InventoryDistribution"]] = relationship(
        back_populates="inventory_item", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("quantity_available")
    def validate_quantity_available(self, key, value):
        return _validate_non_negative(value, "quantity_available")

    def __repr__(self) -> str:
        return f"<InventoryItem id={self.id} name={self.item_name!r} qty={self.quantity_available}>"


# ---------------------------------------------------------------------------
# inventory_distributions
# ---------------------------------------------------------------------------
class InventoryDistribution(Base):
    __tablename__ = "inventory_distributions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inventory_distributions_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    beneficiary_id: Mapped[int] = mapped_column(
        ForeignKey("beneficiaries.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    distributed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(String)

    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="distributions")
    beneficiary: Mapped["Beneficiary"] = relationship(back_populates="distributions")

    @validates("quantity")
    def validate_quantity(self, key, value):
        return _validate_positive(value, "quantity")

    def __repr__(self) -> str:
        return f"<InventoryDistribution id={self.id} qty={self.quantity}>"


# ---------------------------------------------------------------------------
# stories
# ---------------------------------------------------------------------------
class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    charity_id: Mapped[int] = mapped_column(
        ForeignKey("charities.id", ondelete="CASCADE"), nullable=False
    )
    beneficiary_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("beneficiaries.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    charity: Mapped["Charity"] = relationship(back_populates="stories")
    beneficiary: Mapped[Optional["Beneficiary"]] = relationship(back_populates="stories")

    @validates("content")
    def validate_content(self, key, value):
        if not value or not value.strip():
            raise ValueError("content must not be empty")
        return value

    def __repr__(self) -> str:
        return f"<Story id={self.id} title={self.title!r}>"


# ---------------------------------------------------------------------------
# donation_reminders  (1-1 with donors)
# ---------------------------------------------------------------------------
class DonationReminder(Base):
    __tablename__ = "donation_reminders"
    __table_args__ = (
        CheckConstraint(
            "day_of_month BETWEEN 1 AND 31", name="ck_donation_reminders_day_of_month_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    day_of_month: Mapped[int] = mapped_column(nullable=False)
    time_of_day: Mapped[time] = mapped_column(nullable=False, default=time(9, 0), server_default="09:00:00")
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    donor: Mapped["Donor"] = relationship(back_populates="donation_reminder")

    @validates("day_of_month")
    def validate_day_of_month(self, key, value):
        if value is None or not (1 <= value <= 31):
            raise ValueError("day_of_month must be between 1 and 31")
        return value

    def __repr__(self) -> str:
        return f"<DonationReminder id={self.id} donor_id={self.donor_id} day={self.day_of_month}>"


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('account_created', 'donation_successful', 'upcoming_payment', "
            "'application_approved', 'application_rejected', 'plan_payment_failed')",
            name="ck_notifications_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    related_entity_id: Mapped[Optional[int]]
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="notifications")

    @validates("type")
    def validate_type(self, key, value):
        allowed = {
            "account_created",
            "donation_successful",
            "upcoming_payment",
            "application_approved",
            "application_rejected",
            "plan_payment_failed",
        }
        if value not in allowed:
            raise ValueError(f"type must be one of {allowed}, got {value!r}")
        return value

    def __repr__(self) -> str:
        return f"<Notification id={self.id} type={self.type!r} is_read={self.is_read}>"