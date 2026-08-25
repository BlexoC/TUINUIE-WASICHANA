"""Idempotently seed a local development database with non-production data."""

from datetime import date, datetime, timezone

from app.app import app, db
from app.models import Beneficiary, Donation, Scholarship, Sponsor, User


def seed() -> None:
    """Insert development fixtures once; safe to run repeatedly."""
    with app.app_context():
        if User.query.filter_by(email="admin@tuinue.test").first() is None:
            admin = User(full_name="Amina Wanjiku", email="admin@tuinue.test", role="admin")
            admin.set_password("ChangeMe123!")
            coordinator = User(full_name="Faith Njeri", email="faith.njeri@tuinue.test", role="coordinator")
            coordinator.set_password("ChangeMe123!")
            impact_trust = Sponsor(name="Grace Mwangi", email="grace.mwangi@example.test", phone="+254 712 345 678")
            elimu = Sponsor(name="Elimu Futures Trust", email="partnerships@elimufutures.example.test", organisation="Elimu Futures Trust")
            beneficiaries = [
                Beneficiary(first_name="Wanjiku", last_name="Kamau", date_of_birth=date(2010, 5, 14), school_name="Kibera Girls Secondary School", county="Nairobi", guardian_name="Mary Kamau", guardian_phone="+254 722 101 202", enrolled_at=date(2024, 1, 8)),
                Beneficiary(first_name="Akinyi", last_name="Otieno", date_of_birth=date(2011, 9, 2), school_name="Kisumu Girls High School", county="Kisumu", guardian_name="Rose Otieno", guardian_phone="+254 711 303 404", enrolled_at=date(2024, 1, 8)),
                Beneficiary(first_name="Chebet", last_name="Kiptoo", date_of_birth=date(2010, 1, 25), school_name="Kapsoya Girls High School", county="Uasin Gishu", guardian_name="Jane Chebet", guardian_phone="+254 733 505 606", enrolled_at=date(2025, 1, 13)),
            ]

            db.session.add_all([admin, coordinator, impact_trust, elimu, *beneficiaries])
            db.session.flush()
            db.session.add_all([
                Scholarship(beneficiary=beneficiaries[0], sponsor=impact_trust, academic_year=2026, amount=45000, notes="Tuition and learning materials."),
                Scholarship(beneficiary=beneficiaries[1], sponsor=elimu, academic_year=2026, amount=50000, notes="Full academic-year support."),
                Scholarship(beneficiary=beneficiaries[2], sponsor=impact_trust, academic_year=2026, amount=42000, status="pending", notes="Awaiting school fee statement."),
                Donation(sponsor=impact_trust, amount=100000, reference="DEV-MPESA-0001", payment_method="M-Pesa", donated_at=datetime(2026, 1, 10, tzinfo=timezone.utc)),
                Donation(sponsor=elimu, amount=150000, reference="DEV-BANK-0001", payment_method="Bank transfer", donated_at=datetime(2026, 2, 3, tzinfo=timezone.utc)),
            ])
            db.session.commit()
            print("Development seed data created.")
        else:
            print("Development seed data already exists; no changes made.")


if __name__ == "__main__":
    seed()
