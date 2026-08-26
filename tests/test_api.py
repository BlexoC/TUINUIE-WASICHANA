import pytest
from backend.app import create_app
from backend.config import TestConfig
from backend.models import db, User, Charity, Beneficiary, Donation

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def test_health_check(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'

def test_auth_registration_and_login(client):
    # Register donor
    reg_res = client.post('/api/auth/register', json={
        'username': 'Wanjiku Test',
        'email': 'wanjiku@test.org',
        'password': 'password123',
        'role': 'donor'
    })
    assert reg_res.status_code == 201
    assert 'access_token' in reg_res.json
    assert reg_res.json['user']['role'] == 'donor'

    # Login
    login_res = client.post('/api/auth/login', json={
        'email': 'wanjiku@test.org',
        'password': 'password123'
    })
    assert login_res.status_code == 200
    assert 'access_token' in login_res.json

def test_charity_registration_and_pagination(client):
    # Create charity
    res = client.post('/api/charities', json={
        'name': 'Heshima Girls Initiative',
        'email': 'contact@heshima.org',
        'mission_statement': 'Providing sustainable dignity kits to remote schools.',
        'target_amount': 500000
    })
    assert res.status_code == 201
    assert res.json['charity']['status'] == 'pending'

    # Get charities pagination
    list_res = client.get('/api/charities?status=all&page=1&per_page=5')
    assert list_res.status_code == 200
    assert 'items' in list_res.json
    assert 'total' in list_res.json
    assert 'page' in list_res.json
    assert list_res.json['page'] == 1

def test_donation_flow(client):
    # First create charity
    ch = client.post('/api/charities', json={
        'name': 'Emergency Dignity Kits',
        'email': 'kits@emergency.org',
        'mission_statement': 'Emergency pads distribution'
    }).json['charity']

    # One-time donation
    don_res = client.post('/api/donations/one-time', json={
        'charity_id': ch['id'],
        'amount': 2500,
        'payment_method': 'mpesa',
        'mpesa_phone': '+254712345678'
    })
    assert don_res.status_code == 201
    assert don_res.json['donation']['amount'] == 2500

def test_beneficiary_management(client):
    # Create charity
    ch = client.post('/api/charities', json={
        'name': 'Sanitary Care Trust',
        'email': 'care@trust.org',
        'mission_statement': 'Sanitary care for all'
    }).json['charity']

    # Add beneficiary
    ben_res = client.post(f"/api/charities/{ch['id']}/beneficiaries", json={
        'full_name': 'Faith Chebet',
        'age': 14,
        'school_name': 'Moi Primary School',
        'grade_level': 'Grade 8',
        'story': 'Aspiring engineer benefiting from dignity kits'
    })
    assert ben_res.status_code == 201
    assert ben_res.json['beneficiary']['full_name'] == 'Faith Chebet'
