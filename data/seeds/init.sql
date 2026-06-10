-- ─────────────────────────────────────────────────────────────────────────
--  HR Assistant — Database Schema
--  Auto-executed by PostgreSQL on first container start (01_schema.sql).
-- ─────────────────────────────────────────────────────────────────────────

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Tables ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employees (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name_ar         VARCHAR(200)    NOT NULL,
    name_en         VARCHAR(200)    NOT NULL,
    email           VARCHAR(255)    UNIQUE NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'employee',
    department      VARCHAR(100),
    job_title_ar    VARCHAR(200),
    job_title_en    VARCHAR(200),
    manager_id      UUID            REFERENCES employees(id),
    hire_date       DATE            NOT NULL,
    salary          NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    phone           VARCHAR(30),
    national_id     VARCHAR(50),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type      VARCHAR(50)     NOT NULL,
    year            INT             NOT NULL,
    total_days      INT             NOT NULL,
    used_days       INT             NOT NULL DEFAULT 0,
    UNIQUE(employee_id, leave_type, year)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type      VARCHAR(50)     NOT NULL,
    start_date      DATE            NOT NULL,
    end_date        DATE            NOT NULL,
    requested_days  INT             NOT NULL DEFAULT 1,
    reason          TEXT,
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending',
    submitted_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    reviewed_by     UUID            REFERENCES employees(id),
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payslips (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id         UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    period_year         INT             NOT NULL,
    period_month        INT             NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    basic_salary        NUMERIC(12, 2)  NOT NULL,
    housing_allowance   NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    transport_allowance NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    other_allowances    NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    deductions          NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    net_salary          NUMERIC(12, 2)  GENERATED ALWAYS AS
                        (basic_salary + housing_allowance + transport_allowance + other_allowances - deductions)
                        STORED,
    currency            VARCHAR(10)     NOT NULL DEFAULT 'SAR',
    payment_date        DATE,
    payment_status      VARCHAR(50)     NOT NULL DEFAULT 'paid',
    issued_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE(employee_id, period_year, period_month)
);

CREATE TABLE IF NOT EXISTS employee_benefits (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id      UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    benefit_type     VARCHAR(100)    NOT NULL,
    provider         VARCHAR(200),
    coverage_details JSONB,
    effective_date   DATE            NOT NULL,
    expiry_date      DATE,
    is_active        BOOLEAN         NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    title           VARCHAR(500),
    started_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID            NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(50)     NOT NULL,
    content     TEXT            NOT NULL,
    intent      VARCHAR(50),
    tool_calls  JSONB,
    sources     JSONB,
    metadata    JSONB,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id         UUID,
    action              VARCHAR(200)    NOT NULL,
    resource            VARCHAR(100),
    resource_owner_id   UUID,
    details             JSONB,
    ip_address          INET,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Attendance Records
CREATE TABLE IF NOT EXISTS attendance_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE            NOT NULL,
    check_in        TIME,
    check_out       TIME,
    status          VARCHAR(50)     NOT NULL DEFAULT 'present',
    -- present | absent | late | half_day | remote
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE(employee_id, work_date)
);

-- Overtime Records
CREATE TABLE IF NOT EXISTS overtime_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id     UUID            NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE            NOT NULL,
    hours           NUMERIC(4, 2)   NOT NULL CHECK (hours > 0 AND hours <= 24),
    reason          TEXT,
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending',
    -- pending | approved | rejected
    approved_by     UUID            REFERENCES employees(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE(employee_id, work_date)
);

-- ── Indexes ───────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_leave_balances_employee   ON leave_balances(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_balances_year       ON leave_balances(employee_id, year);
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee   ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status     ON leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_payslips_employee         ON payslips(employee_id);
CREATE INDEX IF NOT EXISTS idx_payslips_period           ON payslips(period_year, period_month);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_employee    ON chat_sessions(employee_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session     ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created     ON chat_messages(created_at ASC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_employee       ON audit_logs(employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created        ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_employee       ON attendance_records(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date           ON attendance_records(employee_id, work_date DESC);
CREATE INDEX IF NOT EXISTS idx_overtime_employee         ON overtime_records(employee_id);
CREATE INDEX IF NOT EXISTS idx_overtime_date             ON overtime_records(employee_id, work_date DESC);
