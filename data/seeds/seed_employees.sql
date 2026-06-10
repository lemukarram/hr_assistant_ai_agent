-- ─────────────────────────────────────────────────────────────────────────
--  HR Assistant — Demo Seed Data  (02_seed.sql)
--  Loaded after 01_schema.sql on first container start.
--  All passwords = bcrypt of "demo1234"
--
--  Employee roster:
--    khalid@company.sa  — HR Director  (no manager)
--    sara@company.sa    — Eng Manager  (reports to Khalid)
--    ahmed@company.sa   — Sr Engineer  (reports to Sara)
--    mona@company.sa    — AI Engineer  (reports to Sara)
--    faisal@company.sa  — HR Specialist (reports to Khalid)
-- ─────────────────────────────────────────────────────────────────────────

-- ── Employees ─────────────────────────────────────────────────────────────
-- Pass 1: top-level (no manager_id FK constraint)
INSERT INTO employees (id, name_ar, name_en, email, password_hash, role, department,
                       job_title_ar, job_title_en, hire_date, salary, is_active)
VALUES
(
    'a0000000-0000-0000-0000-000000000001',
    'خالد العتيبي', 'Khalid Al-Otaibi',
    'khalid@company.sa',
    crypt('demo1234', gen_salt('bf')),
    'hr_admin', 'الموارد البشرية',
    'مدير الموارد البشرية', 'HR Director',
    '2019-03-15', 28000.00, TRUE
)
ON CONFLICT (email) DO NOTHING;

-- Pass 2: employees that reference the rows above
INSERT INTO employees (id, name_ar, name_en, email, password_hash, role, department,
                       job_title_ar, job_title_en, manager_id, hire_date, salary, is_active)
VALUES
(
    'a0000000-0000-0000-0000-000000000002',
    'سارة القحطاني', 'Sara Al-Qahtani',
    'sara@company.sa',
    crypt('demo1234', gen_salt('bf')),
    'manager', 'هندسة البرمجيات',
    'مديرة هندسة البرمجيات', 'Software Engineering Manager',
    'a0000000-0000-0000-0000-000000000001',
    '2020-07-01', 22000.00, TRUE
),
(
    'a0000000-0000-0000-0000-000000000005',
    'فيصل الدوسري', 'Faisal Al-Dosari',
    'faisal@company.sa',
    crypt('demo1234', gen_salt('bf')),
    'employee', 'الموارد البشرية',
    'أخصائي موارد بشرية', 'HR Specialist',
    'a0000000-0000-0000-0000-000000000001',
    '2021-01-10', 11500.00, TRUE
)
ON CONFLICT (email) DO NOTHING;

-- Pass 3: employees that report to Sara
INSERT INTO employees (id, name_ar, name_en, email, password_hash, role, department,
                       job_title_ar, job_title_en, manager_id, hire_date, salary, is_active)
VALUES
(
    'a0000000-0000-0000-0000-000000000003',
    'أحمد الشمري', 'Ahmed Al-Shammari',
    'ahmed@company.sa',
    crypt('demo1234', gen_salt('bf')),
    'employee', 'هندسة البرمجيات',
    'مهندس برمجيات أول', 'Senior Software Engineer',
    'a0000000-0000-0000-0000-000000000002',
    '2021-09-15', 15000.00, TRUE
),
(
    'a0000000-0000-0000-0000-000000000004',
    'منى الزهراني', 'Mona Al-Zahrani',
    'mona@company.sa',
    crypt('demo1234', gen_salt('bf')),
    'employee', 'هندسة البرمجيات',
    'مهندسة ذكاء اصطناعي', 'AI Engineer',
    'a0000000-0000-0000-0000-000000000002',
    '2022-02-28', 14000.00, TRUE
)
ON CONFLICT (email) DO NOTHING;

-- ── Leave Balances (current + previous year) ──────────────────────────────
-- Use a function-like approach to seed both 2024 and 2025

DO $$
DECLARE
    cur_year INT := EXTRACT(YEAR FROM CURRENT_DATE)::INT;
    prev_year INT := cur_year - 1;
BEGIN

-- Ahmed
INSERT INTO leave_balances (employee_id, leave_type, year, total_days, used_days)
VALUES
    ('a0000000-0000-0000-0000-000000000003', 'annual',    cur_year,  21, 7),
    ('a0000000-0000-0000-0000-000000000003', 'sick',       cur_year,  30, 3),
    ('a0000000-0000-0000-0000-000000000003', 'emergency',  cur_year,  5,  0),
    ('a0000000-0000-0000-0000-000000000003', 'hajj',       cur_year,  15, 0),
    ('a0000000-0000-0000-0000-000000000003', 'annual',    prev_year, 21, 21),
    ('a0000000-0000-0000-0000-000000000003', 'sick',       prev_year, 30, 5)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

-- Sara
INSERT INTO leave_balances (employee_id, leave_type, year, total_days, used_days)
VALUES
    ('a0000000-0000-0000-0000-000000000002', 'annual',    cur_year,  21, 5),
    ('a0000000-0000-0000-0000-000000000002', 'sick',       cur_year,  30, 0),
    ('a0000000-0000-0000-0000-000000000002', 'emergency',  cur_year,  5,  2)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

-- Khalid
INSERT INTO leave_balances (employee_id, leave_type, year, total_days, used_days)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'annual',    cur_year,  21, 10),
    ('a0000000-0000-0000-0000-000000000001', 'sick',       cur_year,  30, 0)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

-- Mona
INSERT INTO leave_balances (employee_id, leave_type, year, total_days, used_days)
VALUES
    ('a0000000-0000-0000-0000-000000000004', 'annual',    cur_year,  21, 14),
    ('a0000000-0000-0000-0000-000000000004', 'sick',       cur_year,  30, 7),
    ('a0000000-0000-0000-0000-000000000004', 'maternity',  cur_year,  70, 0)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

-- Faisal
INSERT INTO leave_balances (employee_id, leave_type, year, total_days, used_days)
VALUES
    ('a0000000-0000-0000-0000-000000000005', 'annual',    cur_year,  21, 3),
    ('a0000000-0000-0000-0000-000000000005', 'sick',       cur_year,  30, 1),
    ('a0000000-0000-0000-0000-000000000005', 'emergency',  cur_year,  5,  0)
ON CONFLICT (employee_id, leave_type, year) DO NOTHING;

END $$;

-- ── Payslips (last 3 months for each employee) ────────────────────────────
DO $$
DECLARE
    rec RECORD;
    offset_months INT;
    py  INT;
    pm  INT;
    calc_date DATE;
BEGIN
    FOR rec IN
        SELECT id, salary, hire_date FROM employees WHERE is_active = TRUE
    LOOP
        FOR offset_months IN 0..2 LOOP
            calc_date := DATE_TRUNC('month', CURRENT_DATE - (offset_months * INTERVAL '1 month'))::DATE;
            py := EXTRACT(YEAR  FROM calc_date)::INT;
            pm := EXTRACT(MONTH FROM calc_date)::INT;

            INSERT INTO payslips (
                employee_id, period_year, period_month,
                basic_salary, housing_allowance, transport_allowance,
                other_allowances, deductions, currency, payment_status, payment_date
            )
            VALUES (
                rec.id, py, pm,
                rec.salary,
                ROUND(rec.salary * 0.25, 2),   -- 25 % housing
                ROUND(rec.salary * 0.10, 2),   -- 10 % transport
                0,
                ROUND(rec.salary * 0.05, 2),   -- 5 % GOSI deduction
                'SAR',
                'paid',
                (DATE_TRUNC('month', calc_date) + INTERVAL '1 month - 1 day')::DATE
            )
            ON CONFLICT (employee_id, period_year, period_month) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;

-- ── Benefits ──────────────────────────────────────────────────────────────
INSERT INTO employee_benefits (employee_id, benefit_type, provider, coverage_details, effective_date, is_active)
SELECT
    e.id,
    b.benefit_type,
    b.provider,
    b.coverage_details::JSONB,
    b.effective_date::DATE,
    TRUE
FROM employees e
CROSS JOIN (
    VALUES
        (
            'health_insurance',
            'بوبا العربية للتأمين',
            '{"plan": "Gold", "coverage_limit_SAR": 500000, "dental": true, "optical": true, "dependents": 3}',
            '2024-01-01'
        ),
        (
            'life_insurance',
            'شركة تكافل الراجحي',
            '{"coverage_SAR": 300000, "beneficiary": "family", "type": "term"}',
            '2024-01-01'
        )
) AS b(benefit_type, provider, coverage_details, effective_date)
ON CONFLICT DO NOTHING;

-- ── Historical Leave Requests ─────────────────────────────────────────────
INSERT INTO leave_requests
    (employee_id, leave_type, start_date, end_date, requested_days, reason, status, submitted_at, reviewed_at)
VALUES
    (
        'a0000000-0000-0000-0000-000000000003',
        'annual', '2024-01-20', '2024-01-26', 7,
        'إجازة عائلية', 'approved',
        '2024-01-15 09:00:00+03', '2024-01-16 10:00:00+03'
    ),
    (
        'a0000000-0000-0000-0000-000000000003',
        'sick', '2024-02-05', '2024-02-07', 3,
        'مرض موسمي', 'approved',
        '2024-02-05 08:00:00+03', '2024-02-05 09:30:00+03'
    ),
    (
        'a0000000-0000-0000-0000-000000000002',
        'annual', '2024-03-10', '2024-03-14', 5,
        'إجازة شخصية', 'approved',
        '2024-03-01 10:00:00+03', '2024-03-02 11:00:00+03'
    )
ON CONFLICT DO NOTHING;

-- ── Attendance Records (last 30 days for Ahmed, Sara, Khalid) ─────────────
DO $$
DECLARE
    day_offset INT;
    work_date  DATE;
    day_name   TEXT;
    ahmed_id   UUID := 'a0000000-0000-0000-0000-000000000003';
    sara_id    UUID := 'a0000000-0000-0000-0000-000000000002';
    khalid_id  UUID := 'a0000000-0000-0000-0000-000000000001';
BEGIN
    FOR day_offset IN 0..29 LOOP
        work_date := CURRENT_DATE - day_offset;
        day_name := TO_CHAR(work_date, 'DY');
        CONTINUE WHEN day_name IN ('SAT', 'SUN');

        -- Ahmed: mostly present, 2 late days, 1 remote
        INSERT INTO attendance_records (employee_id, work_date, check_in, check_out, status)
        VALUES (
            ahmed_id, work_date,
            CASE
                WHEN day_offset = 5  THEN '08:45:00'
                WHEN day_offset = 12 THEN '09:05:00'
                ELSE '08:00:00'
            END,
            '17:00:00',
            CASE
                WHEN day_offset = 5  THEN 'late'
                WHEN day_offset = 12 THEN 'late'
                WHEN day_offset = 8  THEN 'remote'
                ELSE 'present'
            END
        ) ON CONFLICT (employee_id, work_date) DO NOTHING;

        -- Sara: mostly present, 1 remote, 1 half day
        INSERT INTO attendance_records (employee_id, work_date, check_in, check_out, status)
        VALUES (
            sara_id, work_date,
            '08:00:00',
            CASE WHEN day_offset = 7 THEN '13:00:00' ELSE '17:00:00' END,
            CASE
                WHEN day_offset = 7  THEN 'half_day'
                WHEN day_offset = 15 THEN 'remote'
                ELSE 'present'
            END
        ) ON CONFLICT (employee_id, work_date) DO NOTHING;

        -- Khalid: always present
        INSERT INTO attendance_records (employee_id, work_date, check_in, check_out, status)
        VALUES (
            khalid_id, work_date, '07:55:00', '17:10:00', 'present'
        ) ON CONFLICT (employee_id, work_date) DO NOTHING;
    END LOOP;
END $$;

-- ── Overtime Records ─────────────────────────────────────────────────────
INSERT INTO overtime_records (employee_id, work_date, hours, reason, status, approved_by)
VALUES
    (
        'a0000000-0000-0000-0000-000000000003',
        CURRENT_DATE - 3, 2.0,
        'إنهاء مهمة عاجلة',
        'approved',
        'a0000000-0000-0000-0000-000000000002'
    ),
    (
        'a0000000-0000-0000-0000-000000000003',
        CURRENT_DATE - 10, 3.5,
        'تسليم مشروع للعميل',
        'approved',
        'a0000000-0000-0000-0000-000000000002'
    ),
    (
        'a0000000-0000-0000-0000-000000000003',
        CURRENT_DATE - 1, 1.5,
        'مراجعة الكود مع الفريق',
        'pending',
        NULL
    ),
    (
        'a0000000-0000-0000-0000-000000000004',
        CURRENT_DATE - 5, 2.0,
        'تطوير نموذج الذكاء الاصطناعي',
        'approved',
        'a0000000-0000-0000-0000-000000000002'
    )
ON CONFLICT (employee_id, work_date) DO NOTHING;
