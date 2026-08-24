from App import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='charity_admin') # donor, charity_admin, admin

class Charity(db.Model):
    __tablename__ = 'charities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    registration_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    total_funds = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "registration_number": self.registration_number,
            "status": self.status,
            "total_funds": self.total_funds,
            "created_at": self.created_at.isoformat()
        }