"""
tests/test_api.py — Integration tests for critical API flows

Run with:
    pytest tests/ -v

Requires TEST_DATABASE_URL pointing to an empty PostgreSQL database.
"""

import pytest
from server import create_app, db as _db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    """Create the Flask test application once per test session."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def rollback_after_test(app):
    """Wrap each test in a transaction that is rolled back afterwards."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection
        yield
        _db.session.remove()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def register(client, role="donor", email=None, username=None):
    email    = email    or f"test_{role}@example.com"
    username = username or f"testuser_{role}"
    resp = client.post("/api/auth/register", json={
        "username": username,
        "email":    email,
        "password": "Test@1234",
        "role":     role,
    })
    return resp


def login(client, email, password="Test@1234"):
    resp = client.post("/api/auth/login", json={
        "email":    email,
        "password": password,
    })
    return resp


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth: Register
# ---------------------------------------------------------------------------
class TestRegister:
    def test_register_donor_success(self, client):
        r = register(client, "donor", "donor1@example.com", "donor1")
        assert r.status_code == 201
        assert r.json["user"]["role"] == "donor"
        assert "access_token" in r.json

    def test_register_charity_success(self, client):
        r = register(client, "charity", "charity1@example.com", "charity1")
        assert r.status_code == 201
        assert r.json["user"]["role"] == "charity"

    def test_register_missing_fields(self, client):
        r = client.post("/api/auth/register", json={"email": "x@x.com"})
        assert r.status_code == 422

    def test_register_weak_password(self, client):
        r = client.post("/api/auth/register", json={
            "username": "weakpw",
            "email":    "weak@example.com",
            "password": "123",
            "role":     "donor",
        })
        assert r.status_code == 422

    def test_register_duplicate_email(self, client):
        register(client, "donor", "dup@example.com", "dup1")
        r = client.post("/api/auth/register", json={
            "username": "dup2",
            "email":    "dup@example.com",
            "password": "Test@1234",
            "role":     "donor",
        })
        assert r.status_code == 409

    def test_register_invalid_role(self, client):
        r = client.post("/api/auth/register", json={
            "username": "badrole",
            "email":    "badrole@x.com",
            "password": "Test@1234",
            "role":     "superuser",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth: Login
# ---------------------------------------------------------------------------
class TestLogin:
    def test_login_success(self, client):
        register(client, "donor", "login_ok@example.com", "login_ok")
        r = login(client, "login_ok@example.com")
        assert r.status_code == 200
        assert "access_token" in r.json

    def test_login_wrong_password(self, client):
        register(client, "donor", "wrongpw@example.com", "wrongpw")
        r = client.post("/api/auth/login", json={
            "email":    "wrongpw@example.com",
            "password": "WRONG",
        })
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = login(client, "nobody@example.com")
        assert r.status_code == 401

    def test_me_endpoint(self, client):
        register(client, "donor", "me_test@example.com", "me_test")
        token = login(client, "me_test@example.com").json["access_token"]
        r = client.get("/api/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json["email"] == "me_test@example.com"

    def test_me_requires_auth(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Charities: public list + apply
# ---------------------------------------------------------------------------
class TestCharities:
    def _seed_charity(self, client):
        """Register a charity user and return their token."""
        register(client, "charity", "ch_test@example.com", "ch_test")
        return login(client, "ch_test@example.com").json["access_token"]

    def test_list_charities_public(self, client):
        r = client.get("/api/charities/")
        assert r.status_code == 200
        assert "items" in r.json

    def test_apply_requires_charity_role(self, client):
        register(client, "donor", "notcharity@example.com", "notcharity")
        token = login(client, "notcharity@example.com").json["access_token"]
        r = client.post("/api/charities/apply",
                        json={"organization_name": "X", "contact_email": "x@x.com"},
                        headers=auth_headers(token))
        assert r.status_code == 403

    def test_apply_charity_success(self, client):
        token = self._seed_charity(client)
        r = client.post("/api/charities/apply", json={
            "organization_name": "Test Foundation",
            "contact_email":     "ch_test@example.com",
            "description":       "A test charity",
        }, headers=auth_headers(token))
        assert r.status_code == 201
        assert "application_id" in r.json

    def test_apply_duplicate_pending(self, client):
        token = self._seed_charity(client)
        payload = {
            "organization_name": "Test Foundation",
            "contact_email":     "ch_test@example.com",
        }
        client.post("/api/charities/apply", json=payload, headers=auth_headers(token))
        r = client.post("/api/charities/apply", json=payload, headers=auth_headers(token))
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Donations
# ---------------------------------------------------------------------------
class TestDonations:
    def _setup(self, client, app):
        """Create donor + charity + charity project in DB, return tokens."""
        from server.models import User, Donor, Charity, CharityApplication
        from werkzeug.security import generate_password_hash

        with app.app_context():
            # Donor
            u_donor = User(
                username="don_seed", email="don_seed@example.com",
                password_hash=generate_password_hash("Test@1234"), role="donor",
            )
            _db.session.add(u_donor)
            _db.session.flush()
            _db.session.add(Donor(user_id=u_donor.id))

            # Charity user
            u_ch = User(
                username="ch_seed", email="ch_seed@example.com",
                password_hash=generate_password_hash("Test@1234"), role="charity",
            )
            _db.session.add(u_ch)
            _db.session.flush()
            app_obj = CharityApplication(
                applicant_user_id=u_ch.id,
                organization_name="Seed Charity",
                contact_email="ch_seed@example.com",
                status="approved",
            )
            _db.session.add(app_obj)
            _db.session.flush()
            ch = Charity(
                user_id=u_ch.id, application_id=app_obj.id,
                name="Seed Charity", contact_email="ch_seed@example.com",
                status="active",
            )
            _db.session.add(ch)
            _db.session.commit()
            return u_donor.id, ch.id

    def test_donation_forbidden_for_non_donor(self, client, app):
        register(client, "charity", "nd_d@example.com", "nd_d")
        token = login(client, "nd_d@example.com").json["access_token"]
        r = client.post("/api/donations/", json={
            "charity_id": 1, "amount": 100,
            "payment_provider": "stripe",
            "provider_transaction_id": "txn_xyz",
        }, headers=auth_headers(token))
        assert r.status_code == 403

    def test_donation_missing_fields(self, client):
        register(client, "donor", "don_miss@example.com", "don_miss")
        token = login(client, "don_miss@example.com").json["access_token"]
        r = client.post("/api/donations/", json={"charity_id": 1},
                        headers=auth_headers(token))
        assert r.status_code == 422

    def test_list_donations_requires_auth(self, client):
        r = client.get("/api/donations/")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class TestNotifications:
    def test_list_requires_auth(self, client):
        r = client.get("/api/notifications/")
        assert r.status_code == 401

    def test_list_returns_empty_for_new_user(self, client):
        register(client, "donor", "notif_test@example.com", "notif_test")
        token = login(client, "notif_test@example.com").json["access_token"]
        r = client.get("/api/notifications/", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json["items"] == []
        assert r.json["unread_count"] == 0


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class TestAdmin:
    def test_admin_endpoints_reject_non_admin(self, client):
        register(client, "donor", "notadmin@example.com", "notadmin")
        token = login(client, "notadmin@example.com").json["access_token"]
        r = client.get("/api/admin/applications", headers=auth_headers(token))
        assert r.status_code == 403

    def test_admin_dashboard_requires_admin(self, client):
        register(client, "donor", "notadmin2@example.com", "notadmin2")
        token = login(client, "notadmin2@example.com").json["access_token"]
        r = client.get("/api/admin/dashboard", headers=auth_headers(token))
        assert r.status_code == 403
