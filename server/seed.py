"""
server/seed.py — Realistic seed data for the Tuinuie Wasichana platform

Run with:
    FLASK_APP=wsgi.py FLASK_ENV=development python -m server.seed

WARNING: Drops and recreates all data. Use only on development databases.
"""
import sqlalchemy as sa
import sys
import os
from datetime import date, datetime, timedelta, time, timezone
# Allow running as: python -m server.seed
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from server import create_app, db
from server.models import (
    User, Donor, Administrator, CharityApplication, ApplicationDocument,
    Charity, CharityProject, PaymentMethod, RecurringDonationPlan, Donation,
    Beneficiary, InventoryItem, InventoryDistribution, Story,
    DonationReminder, Notification,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _pw(plain: str) -> str:
    return generate_password_hash(plain)


def _ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def run_seed():
    app = create_app("development")
    with app.app_context():
        print("⚠  Clearing development database …")

        # Drop views first because they depend on the tables.
        db.session.execute(sa.text("DROP VIEW IF EXISTS project_totals"))
        db.session.execute(sa.text("DROP VIEW IF EXISTS charity_totals"))
        db.session.commit()

        # Now it is safe to drop the SQLAlchemy tables.
        db.drop_all()

        print("✔  Creating tables …")
        db.create_all()
        # ── 1. USERS ──────────────────────────────────────────────────────────
        admin_user = User(
            username="superadmin",
            email="admin@tuinuie.org",
            password_hash=_pw("Admin@1234"),
            role="admin",
            first_name="Super",
            last_name="Admin",
            is_active=True,
        )

        # Donor users
        donor1 = User(
            username="amina_k",
            email="amina.kamau@example.com",
            password_hash=_pw("Donor@1234"),
            role="donor",
            first_name="Amina",
            last_name="Kamau",
            phone="+254711000001",
        )
        donor2 = User(
            username="brian_o",
            email="brian.otieno@example.com",
            password_hash=_pw("Donor@1234"),
            role="donor",
            first_name="Brian",
            last_name="Otieno",
            phone="+254722000002",
        )
        donor3 = User(
            username="cynthia_w",
            email="cynthia.wanjiku@example.com",
            password_hash=_pw("Donor@1234"),
            role="donor",
            first_name="Cynthia",
            last_name="Wanjiku",
        )

        # Charity account users
        charity_user1 = User(
            username="girlsrise",
            email="info@girlsrise.org",
            password_hash=_pw("Charity@1234"),
            role="charity",
            first_name="Girls",
            last_name="Rise",
        )
        charity_user2 = User(
            username="masomo_girls",
            email="info@masomogirls.ke",
            password_hash=_pw("Charity@1234"),
            role="charity",
            first_name="Masomo",
            last_name="Girls",
        )
        # A pending applicant (not yet approved)
        applicant_user = User(
            username="pendingcharity",
            email="pending@safeplace.ke",
            password_hash=_pw("Charity@1234"),
            role="charity",
            first_name="Safe",
            last_name="Place",
        )

        db.session.add_all([
            admin_user, donor1, donor2, donor3,
            charity_user1, charity_user2, applicant_user
        ])
        db.session.flush()

        # ── 2. PROFILES ───────────────────────────────────────────────────────
        admin_profile = Administrator(user_id=admin_user.id)

        donor_profile1 = Donor(user_id=donor1.id, default_anonymous=False)
        donor_profile2 = Donor(user_id=donor2.id, default_anonymous=True)
        donor_profile3 = Donor(user_id=donor3.id, default_anonymous=False)

        db.session.add_all([
            admin_profile, donor_profile1, donor_profile2, donor_profile3
        ])
        db.session.flush()

        # ── 3. CHARITY APPLICATIONS ───────────────────────────────────────────
        # Approved application for Girls Rise
        app1 = CharityApplication(
            applicant_user_id=charity_user1.id,
            organization_name="Girls Rise Foundation",
            description="Empowering adolescent girls through menstrual health education and supplies.",
            mission_statement="No girl should miss school because of her period.",
            registration_number="NGO/2022/004817",
            contact_email="info@girlsrise.org",
            contact_phone="+254700112233",
            address="Kibera, Nairobi, Kenya",
            status="approved",
            reviewed_by=admin_profile.id,
            reviewed_at=_ago(60),
        )
        # Approved application for Masomo Girls
        app2 = CharityApplication(
            applicant_user_id=charity_user2.id,
            organization_name="Masomo Girls Initiative",
            description="Providing bursaries, sanitary products, and mentorship to girls in public schools.",
            mission_statement="Every girl deserves an equal chance at education.",
            registration_number="NGO/2021/003322",
            contact_email="info@masomogirls.ke",
            contact_phone="+254733445566",
            address="Kisumu, Kenya",
            status="approved",
            reviewed_by=admin_profile.id,
            reviewed_at=_ago(90),
        )
        # Pending application
        app3 = CharityApplication(
            applicant_user_id=applicant_user.id,
            organization_name="Safe Place for Girls",
            description="Refuge and rehabilitation for girls escaping early marriage.",
            mission_statement="Safety first, always.",
            contact_email="pending@safeplace.ke",
            status="pending",
        )
        db.session.add_all([app1, app2, app3])
        db.session.flush()

        # Documents for pending app
        db.session.add_all([
            ApplicationDocument(
                application_id=app3.id,
                document_type="registration_certificate",
                file_name="reg_cert.pdf",
                file_url="https://storage.tuinuie.org/docs/reg_cert_safeplace.pdf",
                mime_type="application/pdf",
                file_size_bytes=204800,
            ),
            ApplicationDocument(
                application_id=app3.id,
                document_type="director_id",
                file_name="director_id.jpg",
                file_url="https://storage.tuinuie.org/docs/director_id_safeplace.jpg",
                mime_type="image/jpeg",
                file_size_bytes=102400,
            ),
        ])

        # ── 4. CHARITIES ──────────────────────────────────────────────────────
        charity1 = Charity(
            user_id=charity_user1.id,
            application_id=app1.id,
            name="Girls Rise Foundation",
            description="Empowering adolescent girls through menstrual health education and supplies.",
            mission_statement="No girl should miss school because of her period.",
            logo_url="https://cdn.tuinuie.org/logos/girlsrise.png",
            website_url="https://girlsrise.org",
            registration_number="NGO/2022/004817",
            contact_email="info@girlsrise.org",
            contact_phone="+254700112233",
            address="Kibera, Nairobi, Kenya",
            status="active",
        )
        charity2 = Charity(
            user_id=charity_user2.id,
            application_id=app2.id,
            name="Masomo Girls Initiative",
            description="Providing bursaries, sanitary products, and mentorship to girls in public schools.",
            mission_statement="Every girl deserves an equal chance at education.",
            logo_url="https://cdn.tuinuie.org/logos/masomogirls.png",
            website_url="https://masomogirls.ke",
            registration_number="NGO/2021/003322",
            contact_email="info@masomogirls.ke",
            contact_phone="+254733445566",
            address="Kisumu, Kenya",
            status="active",
        )
        db.session.add_all([charity1, charity2])
        db.session.flush()

        # ── 5. PROJECTS ───────────────────────────────────────────────────────
        proj1 = CharityProject(
            charity_id=charity1.id,
            title="Emergency Dignity Kits Distribution — Kibera",
            description="Providing sanitary towels, soap, and underwear to 500 girls in Kibera slum schools.",
            category="Menstrual Health",
            image_url="https://cdn.tuinuie.org/projects/dignity_kits.jpg",
            goal_amount=150000.00,
            is_urgent=True,
            status="active",
        )
        proj2 = CharityProject(
            charity_id=charity1.id,
            title="Puberty Education Workshops",
            description="Monthly workshops on puberty, hygiene, and reproductive health for girls aged 10–14.",
            category="Education",
            image_url="https://cdn.tuinuie.org/projects/workshops.jpg",
            goal_amount=80000.00,
            is_urgent=False,
            status="active",
        )
        proj3 = CharityProject(
            charity_id=charity2.id,
            title="School Bursary Fund 2026",
            description="Secondary school bursaries for 100 girls from low-income families in Kisumu County.",
            category="Education",
            image_url="https://cdn.tuinuie.org/projects/bursary.jpg",
            goal_amount=500000.00,
            is_urgent=False,
            status="active",
        )
        proj4 = CharityProject(
            charity_id=charity2.id,
            title="Sanitary Towel Distribution — Rural Schools",
            description="Monthly supply of sanitary towels to 20 rural primary schools.",
            category="Menstrual Health",
            goal_amount=120000.00,
            is_urgent=True,
            status="active",
        )
        db.session.add_all([proj1, proj2, proj3, proj4])
        db.session.flush()

        # ── 6. PAYMENT METHODS ────────────────────────────────────────────────
        pm1 = PaymentMethod(
            donor_id=donor_profile1.id,
            provider="stripe",
            provider_customer_id="cus_AmK001testXYZ",
            provider_payment_method_id="pm_AmK001cardABC",
            is_default=True,
        )
        pm2 = PaymentMethod(
            donor_id=donor_profile2.id,
            provider="stripe",
            provider_customer_id="cus_BrO002testXYZ",
            provider_payment_method_id="pm_BrO002cardABC",
            is_default=True,
        )
        pm3 = PaymentMethod(
            donor_id=donor_profile3.id,
            provider="paypal",
            provider_customer_id="pp_CyW003testXYZ",
            provider_payment_method_id="pp_CyW003billABC",
            is_default=True,
        )
        db.session.add_all([pm1, pm2, pm3])
        db.session.flush()

        # ── 7. RECURRING PLANS ────────────────────────────────────────────────
        plan1 = RecurringDonationPlan(
            donor_id=donor_profile1.id,
            charity_id=charity1.id,
            project_id=proj1.id,
            payment_method_id=pm1.id,
            amount=2000.00,
            currency="KES",
            frequency="monthly",
            day_of_month=5,
            start_date=date(2026, 1, 5),
            next_donation_date=date(2026, 9, 5),
            status="active",
            is_anonymous=False,
        )
        plan2 = RecurringDonationPlan(
            donor_id=donor_profile2.id,
            charity_id=charity2.id,
            project_id=proj3.id,
            payment_method_id=pm2.id,
            amount=5000.00,
            currency="KES",
            frequency="quarterly",
            start_date=date(2026, 1, 1),
            next_donation_date=date(2026, 10, 1),
            status="active",
            is_anonymous=True,
        )
        plan3 = RecurringDonationPlan(
            donor_id=donor_profile3.id,
            charity_id=charity1.id,
            payment_method_id=pm3.id,
            amount=500.00,
            currency="KES",
            frequency="weekly",
            start_date=date(2026, 7, 1),
            next_donation_date=date(2026, 9, 1),
            status="paused",
            is_anonymous=False,
        )
        db.session.add_all([plan1, plan2, plan3])
        db.session.flush()

        # ── 8. DONATIONS ──────────────────────────────────────────────────────
        donations_data = [
            # (donor, charity, project, plan, type, amount, currency, provider, txn_id, status, is_anon)
            (donor_profile1, charity1, proj1, plan1, "recurring", 2000.00, "KES", "stripe", "txn_001", "completed", False),
            (donor_profile1, charity1, proj1, plan1, "recurring", 2000.00, "KES", "stripe", "txn_002", "completed", False),
            (donor_profile1, charity1, proj1, plan1, "recurring", 2000.00, "KES", "stripe", "txn_003", "completed", False),
            (donor_profile2, charity2, proj3, plan2, "recurring", 5000.00, "KES", "stripe", "txn_004", "completed", True),
            (donor_profile2, charity2, proj3, plan2, "recurring", 5000.00, "KES", "stripe", "txn_005", "completed", True),
            (donor_profile3, charity1, None,  None,  "one_time",  10000.00,"KES", "paypal", "txn_006", "completed", False),
            (donor_profile3, charity2, proj4, None,  "one_time",  3000.00, "KES", "paypal", "txn_007", "completed", False),
            (donor_profile1, charity2, None,  None,  "one_time",  1500.00, "KES", "stripe", "txn_008", "completed", False),
            (donor_profile2, charity1, proj2, None,  "one_time",  2500.00, "KES", "stripe", "txn_009", "failed",    True),
        ]
        donation_objects = []
        for i, (don, char, proj, plan, dtype, amt, cur, prov, txn, stat, anon) in enumerate(donations_data):
            d = Donation(
                donor_id=don.id,
                charity_id=char.id,
                project_id=proj.id if proj else None,
                recurring_plan_id=plan.id if plan else None,
                donation_type=dtype,
                amount=amt,
                currency=cur,
                is_anonymous=anon,
                payment_provider=prov,
                provider_transaction_id=txn,
                payment_status=stat,
                donated_at=_ago(30 - i * 3),
            )
            donation_objects.append(d)
        db.session.add_all(donation_objects)
        db.session.flush()

        # ── 9. BENEFICIARIES ──────────────────────────────────────────────────
        beneficiaries = [
            Beneficiary(
                charity_id=charity1.id,
                full_name="Zawadi Achieng",
                age=14,
                gender="female",
                location="Olympic Primary School, Kibera",
                description="Zawadi missed three days of school every month due to lack of sanitary products. "
                            "After joining the program she has maintained 100% attendance.",
                photo_url="https://cdn.tuinuie.org/beneficiaries/zawadi.jpg",
            ),
            Beneficiary(
                charity_id=charity1.id,
                full_name="Precious Nyambura",
                age=13,
                gender="female",
                location="Olympic Primary School, Kibera",
                description="Precious is now a peer educator in her school after completing the puberty workshop.",
                photo_url="https://cdn.tuinuie.org/beneficiaries/precious.jpg",
            ),
            Beneficiary(
                charity_id=charity2.id,
                full_name="Sharon Atieno",
                age=16,
                gender="female",
                location="Kisumu Girls High School",
                description="Sharon received a full secondary school bursary and is excelling in Sciences.",
                photo_url="https://cdn.tuinuie.org/beneficiaries/sharon.jpg",
            ),
            Beneficiary(
                charity_id=charity2.id,
                full_name="Mercy Onyango",
                age=15,
                gender="female",
                location="Nyalenda Community School, Kisumu",
                description="Mercy plans to study nursing and serve her community.",
            ),
        ]
        db.session.add_all(beneficiaries)
        db.session.flush()

        # ── 10. INVENTORY ─────────────────────────────────────────────────────
        inv_items = [
            InventoryItem(charity_id=charity1.id, item_name="Sanitary Towels (pack of 10)", category="Menstrual Health", unit="pack", quantity_available=850),
            InventoryItem(charity_id=charity1.id, item_name="Biodegradable Soap Bar",       category="Hygiene",          unit="bar",  quantity_available=400),
            InventoryItem(charity_id=charity1.id, item_name="Cotton Underwear (medium)",    category="Clothing",         unit="piece",quantity_available=200),
            InventoryItem(charity_id=charity2.id, item_name="Sanitary Towels (pack of 10)", category="Menstrual Health", unit="pack", quantity_available=600),
            InventoryItem(charity_id=charity2.id, item_name="Exercise Books (pack of 5)",   category="Stationery",       unit="pack", quantity_available=300),
        ]
        db.session.add_all(inv_items)
        db.session.flush()

        # Distribution log
        db.session.add_all([
            InventoryDistribution(inventory_item_id=inv_items[0].id, beneficiary_id=beneficiaries[0].id, quantity=3, notes="Monthly allocation"),
            InventoryDistribution(inventory_item_id=inv_items[1].id, beneficiary_id=beneficiaries[0].id, quantity=2, notes="Hygiene kit"),
            InventoryDistribution(inventory_item_id=inv_items[0].id, beneficiary_id=beneficiaries[1].id, quantity=3, notes="Monthly allocation"),
            InventoryDistribution(inventory_item_id=inv_items[3].id, beneficiary_id=beneficiaries[2].id, quantity=3, notes="Monthly school supply"),
            InventoryDistribution(inventory_item_id=inv_items[4].id, beneficiary_id=beneficiaries[2].id, quantity=2, notes="Term stationery"),
        ])

        # ── 11. STORIES ───────────────────────────────────────────────────────
        db.session.add_all([
            Story(
                charity_id=charity1.id,
                beneficiary_id=beneficiaries[0].id,
                title="From Absence to Excellence: Zawadi's Journey",
                content=(
                    "Before joining the Girls Rise program, Zawadi Achieng lost nearly three days "
                    "of school every month because she had no sanitary towels. Her teachers noticed "
                    "her falling behind and reached out to our outreach team. Since receiving monthly "
                    "dignity kits, Zawadi has not missed a single day of school. She now ranks in the "
                    "top five of her class and dreams of becoming a doctor."
                ),
                image_url="https://cdn.tuinuie.org/stories/zawadi_story.jpg",
                published_at=_ago(15),
            ),
            Story(
                charity_id=charity2.id,
                beneficiary_id=beneficiaries[2].id,
                title="Sharon's Bursary Opens the Door to Science",
                content=(
                    "Sharon Atieno's mother, a casual labourer, could not afford the KES 42,000 "
                    "annual school fees for Kisumu Girls. With the Masomo Girls bursary, Sharon "
                    "enrolled and has since emerged as the best Chemistry student in her Form 2 class. "
                    "She says she wants to become a pharmacist and return to serve Nyalenda."
                ),
                image_url="https://cdn.tuinuie.org/stories/sharon_story.jpg",
                published_at=_ago(5),
            ),
            Story(
                charity_id=charity1.id,
                beneficiary_id=None,
                title="500 Dignity Kits Delivered in Kibera",
                content=(
                    "Our largest single distribution to date: 500 dignity kits — each containing "
                    "three packs of sanitary towels, two bars of soap, and a pair of underwear — "
                    "reached girls across eight primary schools in Kibera in a single Saturday morning."
                ),
                published_at=_ago(2),
            ),
        ])

        # ── 12. DONATION REMINDERS ────────────────────────────────────────────
        db.session.add_all([
            DonationReminder(donor_id=donor_profile1.id, day_of_month=5,  time_of_day=time(8, 0),  is_enabled=True),
            DonationReminder(donor_id=donor_profile3.id, day_of_month=15, time_of_day=time(10, 0), is_enabled=True),
        ])

        # ── 13. NOTIFICATIONS ─────────────────────────────────────────────────
        db.session.add_all([
            Notification(user_id=donor1.id, type="account_created",    title="Welcome to Tuinuie Wasichana!", message="Your donor account is ready.", is_read=True),
            Notification(user_id=donor1.id, type="donation_successful", title="Donation confirmed", message="Your donation of KES 2,000 to Girls Rise Foundation was received.", is_read=False, related_entity_type="donation", related_entity_id=donation_objects[0].id),
            Notification(user_id=donor2.id, type="account_created",    title="Welcome to Tuinuie Wasichana!", message="Your donor account is ready.", is_read=True),
            Notification(user_id=charity_user1.id, type="application_approved", title="Your charity was approved!", message="Girls Rise Foundation is now live on the platform.", is_read=True),
            Notification(user_id=charity_user2.id, type="application_approved", title="Your charity was approved!", message="Masomo Girls Initiative is now live on the platform.", is_read=True),
        ])

        db.session.commit()
        print("✅  Seed complete!")
        print(f"   Users:        {User.query.count()}")
        print(f"   Charities:    {Charity.query.count()}")
        print(f"   Projects:     {CharityProject.query.count()}")
        print(f"   Donations:    {Donation.query.count()}")
        print(f"   Beneficiaries:{Beneficiary.query.count()}")
        print(f"   Stories:      {Story.query.count()}")
        print()
        print("Default credentials:")
        print("  Admin:   admin@tuinuie.org     / Admin@1234")
        print("  Donor:   amina.kamau@example.com / Donor@1234")
        print("  Charity: info@girlsrise.org    / Charity@1234")


if __name__ == "__main__":
    run_seed()
