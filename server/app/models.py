"""Core development data model for Tuinue Wasichana."""

from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.app import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Beneficiary(db.Model):
    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    school_name = db.Column(db.String(160), nullable=False)
    county = db.Column(db.String(80), nullable=False)
    guardian_name = db.Column(db.String(120), nullable=False)
    guardian_phone = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="active")
    enrolled_at = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    scholarships = db.relationship(
        "Scholarship", back_populates="beneficiary", cascade="all, delete-orphan"
    )


class Sponsor(db.Model):
    __tablename__ = "sponsors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30))
    organisation = db.Column(db.String(160))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    scholarships = db.relationship("Scholarship", back_populates="sponsor")
    donations = db.relationship("Donation", back_populates="sponsor")


class Scholarship(db.Model):
    __tablename__ = "scholarships"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey("beneficiaries.id"), nullable=False, index=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey("sponsors.id"), index=True)
    academic_year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="approved")
    awarded_at = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text)

    beneficiary = db.relationship("Beneficiary", back_populates="scholarships")
    sponsor = db.relationship("Sponsor", back_populates="scholarships")


class Donation(db.Model):
    __tablename__ = "donations"

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(db.Integer, db.ForeignKey("sponsors.id"), index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="KES")
    donated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    reference = db.Column(db.String(80), nullable=False, unique=True)
    payment_method = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)

    sponsor = db.relationship("Sponsor", back_populates="donations")


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit = db.Column(db.String(30), nullable=False, default="items")
    category = db.Column(db.String(80), nullable=False, default="general")
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
