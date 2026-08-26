-- ============================================================
-- Recurring Charity Donation Platform — PostgreSQL Schema
-- ============================================================

-- Enable UUID/crypto helpers if you switch to UUID PKs later
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------
CREATE TYPE user_role AS ENUM ('donor', 'charity', 'admin');
CREATE TYPE application_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE charity_status AS ENUM ('active', 'suspended');
CREATE TYPE plan_status AS ENUM ('active', 'paused', 'cancelled');
CREATE TYPE plan_frequency AS ENUM ('weekly', 'monthly', 'quarterly', 'yearly');
CREATE TYPE donation_type AS ENUM ('one_time', 'recurring');
CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
CREATE TYPE payment_provider AS ENUM ('stripe', 'paypal');
CREATE TYPE project_status AS ENUM ('active', 'completed', 'archived');
CREATE TYPE document_type AS ENUM ('registration_certificate', 'financial_audit', 'director_id', 'other');
CREATE TYPE notification_type AS ENUM (
    'account_created', 'donation_successful', 'upcoming_payment',
    'application_approved', 'application_rejected', 'plan_payment_failed'
);

-- ------------------------------------------------------------
-- CORE IDENTITY
-- ------------------------------------------------------------
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    phone           VARCHAR(30),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_role ON users(role);

-- ------------------------------------------------------------
-- DONOR PROFILE
-- ------------------------------------------------------------
CREATE TABLE donors (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    default_anonymous       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- ADMINISTRATOR PROFILE
-- ------------------------------------------------------------
CREATE TABLE administrators (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- CHARITY APPLICATION -> APPROVAL WORKFLOW
-- ------------------------------------------------------------
CREATE TABLE charity_applications (
    id                  BIGSERIAL PRIMARY KEY,
    applicant_user_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_name   VARCHAR(255) NOT NULL,
    description         TEXT,
    mission_statement   TEXT,
    registration_number VARCHAR(100),
    contact_email       VARCHAR(255) NOT NULL,
    contact_phone       VARCHAR(30),
    address             TEXT,
    status              application_status NOT NULL DEFAULT 'pending',
    reviewed_by         BIGINT REFERENCES administrators(id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_charity_applications_status ON charity_applications(status);

-- ------------------------------------------------------------
-- CHARITY APPLICATION VERIFICATION DOCUMENTS
-- (registration certificate, financial audit, director ID, etc.
-- uploaded by the applicant for admin review)
-- ------------------------------------------------------------
CREATE TABLE application_documents (
    id              BIGSERIAL PRIMARY KEY,
    application_id  BIGINT NOT NULL REFERENCES charity_applications(id) ON DELETE CASCADE,
    document_type   document_type NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_url        VARCHAR(500) NOT NULL,
    mime_type       VARCHAR(100),
    file_size_bytes BIGINT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX 

idx_application_documents_application 

ON 

application_documents(application_id);

-- ------------------------------------------------------------
-- LIVE CHARITIES (created once an application is approved)
-- ------------------------------------------------------------
CREATE TABLE charities (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    application_id          BIGINT UNIQUE REFERENCES charity_applications(id) ON DELETE SET NULL,
    name                    VARCHAR(255) NOT NULL,
    description             TEXT,
    mission_statement       TEXT,
    logo_url                VARCHAR(500),
    website_url             VARCHAR(500),
    registration_number     VARCHAR(100),
    contact_email           VARCHAR(255),
    contact_phone           VARCHAR(30),
    address                 TEXT,
    status                  charity_status NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_charities_status ON charities(status);

-- ------------------------------------------------------------
-- CHARITY PROJECTS / CAMPAIGNS
-- (e.g. "Emergency Dignity Kits Distribution" — a fundable initiative
-- within a charity, with its own goal and progress, shown on the
-- charity's "Active Projects" page)
-- ------------------------------------------------------------
CREATE TABLE charity_projects (
    id              BIGSERIAL PRIMARY KEY,
    charity_id      BIGINT NOT NULL REFERENCES charities(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    category        VARCHAR(100),
    image_url       VARCHAR(500),
    goal_amount     NUMERIC(10,2) NOT NULL CHECK (goal_amount > 0),
    is_urgent       BOOLEAN NOT NULL DEFAULT FALSE,
    status          project_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_charity ON charity_projects(charity_id);
CREATE INDEX idx_projects_status ON charity_projects(status);

-- ------------------------------------------------------------
-- SAVED PAYMENT METHODS (Stripe/PayPal tokens only — no raw card data)
-- ------------------------------------------------------------
CREATE TABLE payment_methods (
    id                          BIGSERIAL PRIMARY KEY,
    donor_id                    BIGINT NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    provider                    payment_provider NOT NULL,
    provider_customer_id        VARCHAR(255) NOT NULL,
    provider_payment_method_id  VARCHAR(255) NOT NULL,
    is_default                  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_payment_method_id)
);

CREATE INDEX idx_payment_methods_donor ON payment_methods(donor_id);

-- ------------------------------------------------------------
-- RECURRING DONATION PLANS (the "subscription")
-- ------------------------------------------------------------
CREATE TABLE recurring_donation_plans (
    id                  BIGSERIAL PRIMARY KEY,
    donor_id            BIGINT NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    charity_id          BIGINT NOT NULL REFERENCES charities(id) ON DELETE CASCADE,
    project_id          BIGINT REFERENCES charity_projects(id) ON DELETE SET NULL,
    payment_method_id   BIGINT NOT NULL REFERENCES payment_methods(id) ON DELETE RESTRICT,
    amount              NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    currency             CHAR(3) NOT NULL DEFAULT 'USD',
    frequency           plan_frequency NOT NULL DEFAULT 'monthly',
    day_of_month        SMALLINT CHECK (day_of_month BETWEEN 1 AND 31),
    start_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    next_donation_date  DATE NOT NULL,
    status              plan_status NOT NULL DEFAULT 'active',
    is_anonymous        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_plans_donor ON recurring_donation_plans(donor_id);
CREATE INDEX idx_plans_charity ON recurring_donation_plans(charity_id);
CREATE INDEX idx_plans_next_run ON recurring_donation_plans(next_donation_date)
    WHERE status = 'active';

-- ------------------------------------------------------------
-- DONATIONS (every actual charge — one-time or plan-generated)
-- ------------------------------------------------------------
CREATE TABLE donations (
    id                      BIGSERIAL PRIMARY KEY,
    donor_id                BIGINT NOT NULL REFERENCES donors(id) ON DELETE RESTRICT,
    charity_id              BIGINT NOT NULL REFERENCES charities(id) ON DELETE RESTRICT,
    project_id              BIGINT REFERENCES charity_projects(id) ON DELETE SET NULL,
    recurring_plan_id       BIGINT REFERENCES recurring_donation_plans(id) ON DELETE SET NULL,
    donation_type           donation_type NOT NULL,
    amount                  NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    currency                CHAR(3) NOT NULL DEFAULT 'USD',
    is_anonymous            BOOLEAN NOT NULL DEFAULT FALSE,
    payment_provider        payment_provider NOT NULL,
    provider_transaction_id VARCHAR(255) NOT NULL,
    payment_status          payment_status NOT NULL DEFAULT 'pending',
    donated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payment_provider, provider_transaction_id)
);

CREATE INDEX idx_donations_donor ON donations(donor_id);
CREATE INDEX idx_donations_charity ON donations(charity_id);
CREATE INDEX idx_donations_project ON donations(project_id);
CREATE INDEX idx_donations_plan ON donations(recurring_plan_id);
CREATE INDEX idx_donations_status ON donations(payment_status);

-- ------------------------------------------------------------
-- BENEFICIARIES
-- ------------------------------------------------------------
CREATE TABLE beneficiaries (
    id              BIGSERIAL PRIMARY KEY,
    charity_id      BIGINT NOT NULL REFERENCES charities(id) ON DELETE CASCADE,
    full_name       VARCHAR(255) NOT NULL,
    age             SMALLINT,
    gender          VARCHAR(30),
    location        VARCHAR(255),
    description     TEXT,
    photo_url       VARCHAR(500),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_beneficiaries_charity ON beneficiaries(charity_id);

-- ------------------------------------------------------------
-- INVENTORY (supplies a charity has: pads, water filters, etc.)
-- ------------------------------------------------------------
CREATE TABLE inventory_items (
    id                  BIGSERIAL PRIMARY KEY,
    charity_id          BIGINT NOT NULL REFERENCES charities(id) ON DELETE CASCADE,
    item_name           VARCHAR(255) NOT NULL,
    category            VARCHAR(100),
    unit                VARCHAR(50),
    quantity_available  INTEGER NOT NULL DEFAULT 0 CHECK (quantity_available >= 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_inventory_charity ON inventory_items(charity_id);

-- Ledger of what was distributed to which beneficiary
CREATE TABLE inventory_distributions (
    id                  BIGSERIAL PRIMARY KEY,
    inventory_item_id   BIGINT NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    beneficiary_id      BIGINT NOT NULL REFERENCES beneficiaries(id) ON DELETE CASCADE,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    distributed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes               TEXT
);

CREATE INDEX idx_distributions_item ON inventory_distributions(inventory_item_id);
CREATE INDEX idx_distributions_beneficiary ON inventory_distributions(beneficiary_id);

-- ------------------------------------------------------------
-- BENEFICIARY IMPACT STORIES
-- ------------------------------------------------------------
CREATE TABLE stories (
    id              BIGSERIAL PRIMARY KEY,
    charity_id      BIGINT NOT NULL REFERENCES charities(id) ON DELETE CASCADE,
    beneficiary_id  BIGINT REFERENCES beneficiaries(id) ON DELETE SET NULL,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    image_url       VARCHAR(500),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_stories_charity ON stories(charity_id);

-- ------------------------------------------------------------
-- DONOR MONTHLY REMINDER PREFERENCE
-- ------------------------------------------------------------
CREATE TABLE donation_reminders (
    id              BIGSERIAL PRIMARY KEY,
    donor_id        BIGINT NOT NULL UNIQUE REFERENCES donors(id) ON DELETE CASCADE,
    day_of_month    SMALLINT NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    time_of_day     TIME NOT NULL DEFAULT '09:00',
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- IN-APP NOTIFICATIONS
-- (drives the Notifications page: account events, donation
-- confirmations, upcoming recurring-payment reminders, application
-- status updates)
-- ------------------------------------------------------------
CREATE TABLE notifications (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                notification_type NOT NULL,
    title               VARCHAR(255) NOT NULL,
    message             TEXT NOT NULL,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    related_entity_type VARCHAR(50),
    related_entity_id   BIGINT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE is_read = FALSE;

-- ------------------------------------------------------------
-- HELPER VIEWS
-- ------------------------------------------------------------

-- Total (completed) donations received per charity
CREATE VIEW charity_totals AS
SELECT
    c.id AS charity_id,
    c.name,
    COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0) AS total_received
FROM charities c
LEFT JOIN donations d ON d.charity_id = c.id
GROUP BY c.id, c.name;

-- Amount raised per project, for progress bars on the Active Projects page
CREATE VIEW project_totals AS
SELECT
    p.id AS project_id,
    p.charity_id,
    p.title,
    p.goal_amount,
    COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0) AS amount_raised,
    ROUND(
        COALESCE(SUM(d.amount) FILTER (WHERE d.payment_status = 'completed'), 0)
        / NULLIF(p.goal_amount, 0) * 100, 1
    ) AS percent_funded
FROM charity_projects p
LEFT JOIN donations d ON d.project_id = p.id
GROUP BY p.id, p.charity_id, p.title, p.goal_amount;
