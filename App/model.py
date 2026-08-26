from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='donor', nullable=False) # 'donor', 'charity', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    charity = db.relationship('Charity', backref='owner', uselist=False, lazy=True)
    donations = db.relationship('Donation', backref='donor', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'charity_id': self.charity.id if self.charity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Charity(db.Model):
    __tablename__ = 'charities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    year_established = db.Column(db.String(10), nullable=True)
    org_type = db.Column(db.String(50), nullable=True)
    mission_statement = db.Column(db.Text, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False) # 'pending', 'approved', 'rejected'
    category = db.Column(db.String(50), default='Sanitary Distribution')
    target_amount = db.Column(db.Numeric(12, 2), default=500000.00)
    raised_amount = db.Column(db.Numeric(12, 2), default=0.00)
    currency = db.Column(db.String(10), default='KES')
    image_url = db.Column(db.String(500), nullable=True)
    ngo_cert_url = db.Column(db.String(500), nullable=True)
    audit_doc_url = db.Column(db.String(500), nullable=True)
    director_id_url = db.Column(db.String(500), nullable=True)
    what_they_do = db.Column(db.Text, nullable=True)
    how_it_started = db.Column(db.Text, nullable=True)
    impact_summary = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    beneficiaries = db.relationship('Beneficiary', backref='charity', lazy=True, cascade='all, delete-orphan')
    donations = db.relationship('Donation', backref='charity', lazy=True)

    def to_dict(self, include_beneficiaries_count=True):
        data = {
            'id': self.id,
            'name': self.name,
            'year_established': self.year_established,
            'org_type': self.org_type,
            'mission_statement': self.mission_statement,
            'address': self.address,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'contact_person': self.contact_person,
            'status': self.status,
            'category': self.category,
            'tag': self.category,
            'target_amount': float(self.target_amount) if self.target_amount else 0,
            'raised_amount': float(self.raised_amount) if self.raised_amount else 0,
            'currency': self.currency,
            'image_url': self.image_url,
            'ngo_cert_url': self.ngo_cert_url,
            'audit_doc_url': self.audit_doc_url,
            'director_id_url': self.director_id_url,
            'what_they_do': self.what_they_do or self.mission_statement,
            'how_it_started': self.how_it_started,
            'impact_summary': self.impact_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_beneficiaries_count:
            data['beneficiaries_count'] = len(self.beneficiaries)
        return data

class Beneficiary(db.Model):
    __tablename__ = 'beneficiaries'
    
    id = db.Column(db.Integer, primary_key=True)
    charity_id = db.Column(db.Integer, db.ForeignKey('charities.id'), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    school_name = db.Column(db.String(150), nullable=False)
    grade_level = db.Column(db.String(50), nullable=False)
    kits_received = db.Column(db.Integer, default=1)
    attendance_rate = db.Column(db.Integer, default=95) # percentage 0-100
    story = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active') # 'active', 'graduated', 'supported'
    last_kit_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'charity_id': self.charity_id,
            'full_name': self.full_name,
            'age': self.age,
            'school_name': self.school_name,
            'grade_level': self.grade_level,
            'kits_received': self.kits_received,
            'attendance_rate': self.attendance_rate,
            'story': self.story,
            'status': self.status,
            'last_kit_date': self.last_kit_date.isoformat() if self.last_kit_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Donation(db.Model):
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    donor_name = db.Column(db.String(120), nullable=True)
    donor_email = db.Column(db.String(120), nullable=True)
    charity_id = db.Column(db.Integer, db.ForeignKey('charities.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default='KES')
    frequency = db.Column(db.String(20), default='one-time') # 'one-time', 'monthly'
    payment_method = db.Column(db.String(20), nullable=False) # 'mpesa', 'stripe'
    payment_status = db.Column(db.String(20), default='pending') # 'pending', 'completed', 'failed'
    mpesa_phone = db.Column(db.String(30), nullable=True)
    mpesa_receipt = db.Column(db.String(50), nullable=True)
    stripe_payment_id = db.Column(db.String(100), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'donor_id': self.donor_id,
            'donor_name': 'Anonymous' if self.is_anonymous else (self.donor_name or (self.donor.username if self.donor else 'Supporter')),
            'donor_email': None if self.is_anonymous else (self.donor_email or (self.donor.email if self.donor else None)),
            'charity_id': self.charity_id,
            'charity_name': self.charity.name if self.charity else 'Tuinue Wasichana Fund',
            'amount': float(self.amount),
            'currency': self.currency,
            'frequency': self.frequency,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'mpesa_receipt': self.mpesa_receipt,
            'is_anonymous': self.is_anonymous,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), default='account') # 'account', 'donation', 'payment', 'charity_status'
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'read': self.read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
