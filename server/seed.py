"""Idempotently seed a local development database with non-production data."""

from datetime import date, datetime, timezone

from app.app import app, db
from werkzeug.security import generate_password_hash

from app.models import (
    Administrator,
    Beneficiary,
    Charity,
    CharityProject,
    Donation,
    Donor,
    Story,
    User,
)


def seed() -> None:
    """Insert development fixtures once; safe to run repeatedly."""
    with app.app_context():
        if db.session.query(User).filter_by(email="admin@tuinue.test").first() is None:
            password_hash = generate_password_hash("ChangeMe123!")
            admin_user = User(username="amina.admin", email="admin@tuinue.test", password_hash=password_hash, role="admin", first_name="Amina", last_name="Wanjiku")
            donor_user = User(username="grace.donor", email="grace.mwangi@example.test", password_hash=password_hash, role="donor", first_name="Grace", last_name="Mwangi")
            charity_user = User(username="tuinue.wasichana", email="contact@tuinue.test", password_hash=password_hash, role="charity", first_name="Tuinue", last_name="Wasichana")
            db.session.add_all([admin_user, donor_user, charity_user])
            db.session.flush()

            admin = Administrator(user=admin_user)
            donor = Donor(user=donor_user)
            charity = Charity(user=charity_user, name="Tuinue Wasichana", description="Development fixture supporting girls' education.", mission_statement="Helping girls remain in school.", contact_email="contact@tuinue.test", contact_phone="+254 700 000 001")
            db.session.add_all([admin, donor, charity])
            db.session.flush()

            project = CharityProject(charity=charity, title="Keep Girls Learning", description="School-fee and learning-material support for girls in Nairobi and Kisumu.", category="Education", goal_amount=500000)
            beneficiaries = [
                Beneficiary(charity=charity, full_name="Wanjiku Kamau", age=16, gender="Female", location="Nairobi", description="Fictional development fixture."),
                Beneficiary(charity=charity, full_name="Akinyi Otieno", age=15, gender="Female", location="Kisumu", description="Fictional development fixture."),
            ]
            db.session.add_all([project, *beneficiaries])
            db.session.flush()
            db.session.add_all([
                Donation(donor=donor, charity=charity, project=project, donation_type="one_time", amount=100000, currency="KES", payment_provider="stripe", provider_transaction_id="dev-stripe-0001", payment_status="completed", donated_at=datetime(2026, 1, 10, tzinfo=timezone.utc)),
                Story(charity=charity, beneficiary=beneficiaries[0], title="A new school year", content="This entirely fictional story is included only for local development.", published_at=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            ])
            db.session.commit()
            print("Development seed data created.")
        else:
            print("Development seed data already exists; no changes made.")


if __name__ == "__main__":
    seed()
