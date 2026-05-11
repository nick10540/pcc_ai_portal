-- PCC AI Portal — Initial Schema
-- สร้างตารางทั้งหมดตามที่ออกแบบไว้

-- ── Users ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    azure_oid     VARCHAR(36) UNIQUE NOT NULL,   -- Azure AD Object ID
    email         VARCHAR(255) UNIQUE NOT NULL,
    department    VARCHAR(100) NOT NULL DEFAULT 'Unknown',
    tier          VARCHAR(20) NOT NULL DEFAULT 'basic'
                  CHECK (tier IN ('basic','standard','pro','power','admin')),
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Audit Logs (ไม่เก็บ content ตาม PDPA) ─────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id),
    model          VARCHAR(50) NOT NULL,
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd       NUMERIC(10,6) NOT NULL DEFAULT 0,
    cost_thb       NUMERIC(10,2) NOT NULL DEFAULT 0,
    pii_detected   BOOLEAN NOT NULL DEFAULT false,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- ── Budget Quotas (ต่อ user) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_quotas (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id),
    period         VARCHAR(7) NOT NULL,   -- YYYY-MM
    quota_tokens   BIGINT,                -- NULL = unlimited
    used_tokens    BIGINT NOT NULL DEFAULT 0,
    quota_thb      NUMERIC(10,2),         -- NULL = unlimited
    used_thb       NUMERIC(10,2) NOT NULL DEFAULT 0,
    UNIQUE (user_id, period)
);

-- ── Department Budgets ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS department_budgets (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department     VARCHAR(100) NOT NULL,
    period         VARCHAR(7) NOT NULL,   -- YYYY-MM
    budget_thb     NUMERIC(10,2) NOT NULL,
    used_thb       NUMERIC(10,2) NOT NULL DEFAULT 0,
    UNIQUE (department, period)
);

-- ── PII Events ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pii_events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id),
    pii_types      JSONB NOT NULL,        -- ["thai_national_id", "thai_phone"]
    action         VARCHAR(20) NOT NULL
                   CHECK (action IN ('warned','blocked')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pii_events_user_id ON pii_events(user_id);

-- ── Dev Seed Data (สำหรับ local testing) ───────────────────────
INSERT INTO users (azure_oid, email, department, tier) VALUES
    ('dev-basic-oid',    'dev-basic@precise.co.th',    'Operations',  'basic'),
    ('dev-standard-oid', 'dev-standard@precise.co.th', 'Engineering', 'standard'),
    ('dev-pro-oid',      'dev-pro@precise.co.th',      'Engineering', 'pro'),
    ('dev-power-oid',    'dev-power@precise.co.th',    'Management',  'power'),
    ('dev-admin-oid',    'dev-admin@precise.co.th',    'IT',          'admin')
ON CONFLICT DO NOTHING;
