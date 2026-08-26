from app.app import create_app, db
from app.models import Base


def test_application_and_models_initialize() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with app.app_context():
        Base.metadata.create_all(db.engine)
        assert "users" in Base.metadata.tables
        Base.metadata.drop_all(db.engine)
