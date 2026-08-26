from datetime import datetime, timezone
from decimal import Decimal

from app.app import create_app, db
from app.models import Donation, Sponsor


def beneficiary_payload(**overrides: str) -> dict:
    payload = {
        "first_name": "Wanjiku",
        "last_name": "Kamau",
        "date_of_birth": "2010-05-14",
        "school_name": "Kibera Girls Secondary School",
        "county": "Nairobi",
        "guardian_name": "Mary Kamau",
        "guardian_phone": "+254722101202",
    }
    payload.update(overrides)
    return payload


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


def test_beneficiary_crud_and_pagination() -> None:
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    client = app.test_client()
    with app.app_context():
        db.create_all()

    create_response = client.post("/api/beneficiaries", json=beneficiary_payload())
    assert create_response.status_code == 201
    beneficiary = create_response.json
    assert beneficiary["id"] == 1
    assert beneficiary["status"] == "active"

    list_response = client.get("/api/beneficiaries?page=1&per_page=1")
    assert list_response.status_code == 200
    assert list_response.json["pagination"] == {"page": 1, "per_page": 1, "total": 1, "pages": 1}
    assert list_response.json["beneficiaries"][0]["id"] == beneficiary["id"]

    update_response = client.put("/api/beneficiaries/1", json={"status": "graduated"})
    assert update_response.status_code == 200
    assert update_response.json["status"] == "graduated"

    delete_response = client.delete("/api/beneficiaries/1")
    assert delete_response.status_code == 204
    assert client.put("/api/beneficiaries/1", json={"status": "active"}).status_code == 404

    with app.app_context():
        db.drop_all()


def test_inventory_crud_and_pagination() -> None:
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    client = app.test_client()
    with app.app_context():
        db.create_all()

    create_response = client.post(
        "/api/inventory",
        json={"name": "Sanitary pads", "quantity": 48, "category": "Hygiene"},
    )
    assert create_response.status_code == 201
    item = create_response.json
    assert item["id"] == 1
    assert item["unit"] == "items"

    list_response = client.get("/api/inventory?page=1&per_page=1")
    assert list_response.status_code == 200
    assert list_response.json["pagination"] == {"page": 1, "per_page": 1, "total": 1, "pages": 1}
    assert list_response.json["inventory"][0]["id"] == item["id"]

    update_response = client.put("/api/inventory/1", json={"quantity": 36})
    assert update_response.status_code == 200
    assert update_response.json["quantity"] == 36

    delete_response = client.delete("/api/inventory/1")
    assert delete_response.status_code == 204
    assert client.put("/api/inventory/1", json={"quantity": 0}).status_code == 404

    with app.app_context():
        db.drop_all()
