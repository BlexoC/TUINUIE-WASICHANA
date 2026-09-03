# Tuinuie Wasichana — Backend API

> **"Tuinuie Wasichana"** (Swahili: *Let us uplift girls*)
>
> A production-ready recurring charity donation platform focused on
> menstrual health, education, and the empowerment of adolescent girls in Kenya.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Quick Start](#quick-start)
4. [Database Migrations](#database-migrations)
5. [Seed Data](#seed-data)
6. [Running the Server](#running-the-server)
7. [API Reference](#api-reference)
8. [Recurring Plan Scheduler](#recurring-plan-scheduler)
9. [Testing](#testing)
10. [Environment Variables](#environment-variables)
11. [Security Notes](#security-notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Client (React / Mobile)                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────────────┐
│  Flask REST API   (Gunicorn — 4 workers)                        │
│                                                                 │
│  /api/auth          JWT register / login / refresh              │
│  /api/charities     Charity CRUD + application workflow         │
│  /api/projects      Campaign projects per charity               │
│  /api/donations     One-time donation recording                 │
│  /api/recurring-plans  Subscription plan management             │
│  /api/payment-methods  Tokenised Stripe / PayPal methods        │
│  /api/beneficiaries    Beneficiary profiles                     │
│  /api/inventory        Supply tracking + distribution log       │
│  /api/stories          Impact story CMS                         │
│  /api/notifications    In-app notification feed                 │
│  /api/admin            Application review + platform stats      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ SQLAlchemy ORM
┌───────────────────────────▼─────────────────────────────────────┐
│  PostgreSQL 16                                                  │
│  17 tables  ·  11 ENUMs  ·  2 views  ·  20+ indexes            │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  Cron / Celery beat   (server/services/scheduler.py)            │
│  Daily: process due recurring plans → charge → notify           │
│  3-day lookahead: send upcoming-payment reminders               │
└─────────────────────────────────────────────────────────────────┘
```

### Role model

| Role      | Can do                                                              |
|-----------|---------------------------------------------------------------------|
| `donor`   | Browse charities/projects, donate, manage recurring plans, notifications |
| `charity` | Manage own profile, projects, beneficiaries, inventory, stories    |
| `admin`   | Review applications, approve/reject, suspend charities, platform stats |

---

## Project Structure

```
tuinuie-wasichana-backend/
├── wsgi.py                         # WSGI entry point (Gunicorn)
├── alembic.ini                     # Alembic configuration
├── requirements.txt
├── .env.example
│
├── server/
│   ├── __init__.py                 # App factory (create_app)
│   ├── config.py                   # Dev / test / production config classes
│   ├── models.py                   # All 17 SQLAlchemy models
│   ├── schemas.sql                 # Raw PostgreSQL DDL (reference)
│   ├── seed.py                     # Development seed script
│   │
│   ├── api/
│   │   ├── middleware/
│   │   │   └── auth.py             # Role guards, ownership decorators
│   │   └── routes/
│   │       ├── auth.py             # /api/auth/*
│   │       ├── users.py            # /api/users/*
│   │       ├── charities.py        # /api/charities/*
│   │       ├── projects.py         # /api/projects/*
│   │       ├── donations.py        # /api/donations/*
│   │       ├── recurring_plans.py  # /api/recurring-plans/*
│   │       ├── payment_methods.py  # /api/payment-methods/*
│   │       ├── beneficiaries.py    # /api/beneficiaries/*
│   │       ├── inventory.py        # /api/inventory/*
│   │       ├── stories.py          # /api/stories/*
│   │       ├── notifications.py    # /api/notifications/*
│   │       └── admin.py            # /api/admin/*
│   │
│   ├── migrations/
│   │   ├── env.py                  # Alembic ↔ Flask wiring
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   │
│   ├── services/
│   │   └── scheduler.py            # Recurring plan processor + CLI commands
│   │
│   └── utils/
│       └── pagination.py           # Offset pagination helper
│
└── tests/
    └── test_api.py                 # Integration test suite
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+

### 1. Clone & create virtual environment

```bash
git clone <repo-url> tuinuie-backend
cd tuinuie-backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY
```

### 3. Create the database

```bash
createdb tuinuie_dev
```

---

## Database Migrations

```bash
# Initialise Alembic (first time only — already done in this repo)
flask db init

# Apply all migrations
flask db upgrade

# Generate a new migration after model changes
flask db migrate -m "add column xyz"
flask db upgrade

# Roll back one revision
flask db downgrade
```

The initial migration (`0001_initial_schema.py`) creates all 17 tables,
11 ENUM types, all indexes (including two partial indexes), and the two
helper views (`charity_totals`, `project_totals`).

---

## Seed Data

```bash
python -m server.seed
```

This drops and recreates all data, then inserts:

| Entity | Count |
|--------|-------|
| Users | 7 (1 admin, 3 donors, 2 charity accounts, 1 pending applicant) |
| Charities | 2 (Girls Rise Foundation, Masomo Girls Initiative) |
| Projects | 4 |
| Donations | 9 (mix of completed, failed, recurring, one-time) |
| Beneficiaries | 4 |
| Stories | 3 |

**Default credentials:**

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@tuinuie.org` | `Admin@1234` |
| Donor | `amina.kamau@example.com` | `Donor@1234` |
| Charity | `info@girlsrise.org` | `Charity@1234` |

---

## Running the Server

### Development

```bash
flask run --debug
# API available at http://localhost:5000
```

### Production (Gunicorn)

```bash
gunicorn "wsgi:app" \
  --workers 4 \
  --worker-class sync \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## API Reference

All endpoints are prefixed with `/api`. Authenticated endpoints require:
```
Authorization: Bearer <access_token>
```

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | — | Register donor or charity user |
| `POST` | `/auth/login` | — | Login, returns JWT tokens |
| `POST` | `/auth/refresh` | refresh token | Get new access token |
| `POST` | `/auth/logout` | ✓ | Client-side logout |
| `GET`  | `/auth/me` | ✓ | Current user's profile |

### Charities

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/charities/` | — | List active charities (paginated, searchable) |
| `GET`  | `/charities/<id>` | — | Charity detail |
| `GET`  | `/charities/<id>/stats` | — | Donation stats |
| `PATCH`| `/charities/<id>` | ✓ owner/admin | Update charity profile |
| `POST` | `/charities/apply` | ✓ charity role | Submit application |

### Projects

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/projects/` | — | List projects (`?charity_id=&status=`) |
| `POST` | `/projects/` | ✓ charity/admin | Create project |
| `GET`  | `/projects/<id>` | — | Project detail + funding progress |
| `PATCH`| `/projects/<id>` | ✓ owner/admin | Update project |
| `DELETE`| `/projects/<id>` | ✓ owner/admin | Archive project |

### Donations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/donations/` | ✓ donor | Record a completed one-time donation |
| `GET`  | `/donations/` | ✓ donor | Donor's own donation history |
| `GET`  | `/donations/<id>` | ✓ | Donation detail |
| `GET`  | `/donations/charity/<id>` | ✓ charity/admin | Charity's received donations |
| `POST` | `/donations/<id>/refund` | ✓ admin | Mark donation as refunded |

### Recurring Plans

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/recurring-plans/` | ✓ donor | Create a recurring plan |
| `GET`  | `/recurring-plans/` | ✓ donor | Donor's own plans |
| `GET`  | `/recurring-plans/<id>` | ✓ | Plan detail |
| `PATCH`| `/recurring-plans/<id>` | ✓ donor/admin | Pause, resume, change amount |
| `DELETE`| `/recurring-plans/<id>` | ✓ donor/admin | Cancel plan |

### Payment Methods

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/payment-methods/` | ✓ donor | List saved methods |
| `POST` | `/payment-methods/` | ✓ donor | Save tokenised method |
| `DELETE`| `/payment-methods/<id>` | ✓ donor | Remove method |
| `PATCH`| `/payment-methods/<id>/default` | ✓ donor | Set as default |

### Beneficiaries

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/beneficiaries/` | — | List (`?charity_id=`) |
| `POST` | `/beneficiaries/` | ✓ charity/admin | Add beneficiary |
| `GET`  | `/beneficiaries/<id>` | — | Detail |
| `PATCH`| `/beneficiaries/<id>` | ✓ owner/admin | Update |
| `DELETE`| `/beneficiaries/<id>` | ✓ owner/admin | Delete |

### Inventory

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/inventory/` | ✓ charity/admin | List items |
| `POST` | `/inventory/` | ✓ charity/admin | Add item |
| `GET`  | `/inventory/<id>` | ✓ | Detail + distribution log |
| `PATCH`| `/inventory/<id>` | ✓ owner/admin | Update item / quantity |
| `DELETE`| `/inventory/<id>` | ✓ owner/admin | Delete item |
| `POST` | `/inventory/<id>/distribute` | ✓ | Record distribution to beneficiary |

### Stories

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/stories/` | — | Published stories (`?charity_id=`) |
| `POST` | `/stories/` | ✓ charity/admin | Create story |
| `GET`  | `/stories/<id>` | — | Story detail |
| `PATCH`| `/stories/<id>` | ✓ owner/admin | Update / publish / unpublish |
| `DELETE`| `/stories/<id>` | ✓ owner/admin | Delete |

### Notifications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/notifications/` | ✓ | Current user's notifications |
| `PATCH`| `/notifications/<id>/read` | ✓ | Mark one as read |
| `POST` | `/notifications/read-all` | ✓ | Mark all as read |
| `DELETE`| `/notifications/<id>` | ✓ | Delete notification |

### Admin (role=admin only)

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/admin/applications` | List applications (`?status=pending`) |
| `GET`  | `/admin/applications/<id>` | Application detail + documents |
| `POST` | `/admin/applications/<id>/approve` | Approve + create Charity record |
| `POST` | `/admin/applications/<id>/reject` | Reject with reason |
| `GET`  | `/admin/users` | List all users |
| `PATCH`| `/admin/users/<id>/deactivate` | Deactivate user |
| `GET`  | `/admin/dashboard` | Platform-wide stats |

---

## Recurring Plan Scheduler

The scheduler (`server/services/scheduler.py`) must be run daily. It:

1. Queries all `active` plans with `next_donation_date <= today`
2. Calls the payment gateway (stub — replace with Stripe SDK)
3. Records a `Donation` row (`completed` or `failed`)
4. Advances `next_donation_date` to the next cycle
5. Fires an in-app notification to the donor

### Run manually (development)

```bash
flask run-scheduler
flask send-reminders --days 3
```

### Production options

**Heroku Scheduler / cron:**
```
0 6 * * * flask run-scheduler && flask send-reminders
```

**Celery beat (recommended for scale):**
```python
# celery_config.py
from celery.schedules import crontab
beat_schedule = {
    "charge-due-plans":   {"task": "tasks.process_due_plans",    "schedule": crontab(hour=6, minute=0)},
    "send-reminders":     {"task": "tasks.send_reminders",       "schedule": crontab(hour=7, minute=0)},
}
```

---

## Testing

```bash
# Create a test database
createdb tuinuie_test
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tuinuie_test

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=server --cov-report=term-missing
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✓ (prod) | dev local | PostgreSQL connection string |
| `SECRET_KEY` | ✓ | `CHANGE_ME_IN_PROD` | Flask session secret |
| `JWT_SECRET_KEY` | ✓ | `CHANGE_ME_JWT_IN_PROD` | JWT signing secret |
| `FLASK_ENV` | — | `development` | `development` / `production` |
| `CORS_ORIGINS` | — | `http://localhost:3000` | Comma-separated allowed origins |
| `TEST_DATABASE_URL` | test only | — | PostgreSQL DB for pytest |

---

## Security Notes

- **No raw card data** passes through this API. Payment methods are stored
  as gateway tokens only (`provider_payment_method_id`).
- **Anonymous donations**: the `is_anonymous` flag is enforced in
  `Donation.to_dict()` — charity-role viewers never see `donor_id` on
  anonymous records.
- **JWT blocklisting**: the current implementation is client-side only.
  For production, implement a Redis blocklist in the `check_if_token_revoked`
  callback in `server/__init__.py`.
- **Password hashing**: Werkzeug's `generate_password_hash` uses
  `scrypt` by default (Python 3.11+), which is recommended.
- **Admin provisioning**: admin accounts must be created directly in the
  database — there is no public registration path for admins.
