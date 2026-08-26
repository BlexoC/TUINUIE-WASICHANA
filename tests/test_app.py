from datetime import datetime, timezone
from decimal import Decimal

from app.app import create_app, db
from app.models import Donation, Sponsor


def test_application_and_models_initialize() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with app.app_context():
        db.create_all()
        assert "users" in db.metadata.tables
        db.drop_all()


def test_charity_donations_lists_named_donors_and_total() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with app.app_context():
        db.create_all()
        sponsor = Sponsor(name="Grace Mwangi", email="grace@example.test")
        db.session.add_all(
            [
                sponsor,
                Donation(
                    sponsor=sponsor,
                    amount=Decimal("1000.00"),
                    reference="named-gift",
                    payment_method="M-Pesa",
                    donated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
                ),
                Donation(
                    amount=Decimal("250.00"),
                    reference="anonymous-gift",
                    payment_method="Card",
                    donated_at=datetime(2026, 1, 11, tzinfo=timezone.utc),
                ),
            ]
        )
        db.session.commit()

    response = app.test_client().get("/api/charity/donations")

    assert response.status_code == 200
    assert response.json == {
        "total_donated": 1250.0,
        "donations": [
            {
                "id": 1,
                "donor_name": "Grace Mwangi",
                "amount": 1000.0,
                "currency": "KES",
                "donated_at": "2026-01-10T00:00:00",
            }
        ],
    }

    with app.app_context():
        db.drop_all()
