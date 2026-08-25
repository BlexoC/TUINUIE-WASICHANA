# Database development

The application uses Flask-Migrate (Alembic) and SQLAlchemy. The SQLite default is
`server/instance/app.db`; set `DATABASE_URL` to use another database.

## First-time setup

From the repository root, install dependencies and run the committed initial migration:

```bash
python3 -m pip install -r requirements.txt
cd server
export FLASK_APP=app.app:app
flask db upgrade
python3 seed.py
```

The seed is idempotent. It inserts development-only data on its first run and
leaves an already-seeded database unchanged. Both test users use `ChangeMe123!`;
never use it outside local development.

## Future schema changes

After changing `app/models.py`, generate, review, and apply a migration:

```bash
cd server
export FLASK_APP=app.app:app
flask db migrate -m "describe the schema change"
flask db upgrade
```

`migrations/` is already initialized and committed. Do not run `flask db init`
again unless deliberately replacing the migration history.
