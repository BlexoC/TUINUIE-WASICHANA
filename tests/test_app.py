from app.app import create_app, db


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
