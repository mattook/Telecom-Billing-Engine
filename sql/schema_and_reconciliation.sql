DROP TABLE IF EXISTS billing_audit_exceptions CASCADE;
DROP TABLE IF EXISTS rated_cdrs CASCADE;
DROP TABLE IF EXISTS supplier_wholesale_bill CASCADE;
DROP TABLE IF EXISTS cdr_usage CASCADE;
DROP TABLE IF EXISTS rate_cards CASCADE;
DROP TABLE IF EXISTS resellers CASCADE;

-- 1. Base Tables
CREATE TABLE resellers (
    reseller_id INT PRIMARY KEY,
    reseller_name VARCHAR(100),
    tier VARCHAR(50)
);

CREATE TABLE rate_cards (
    prefix VARCHAR(20) PRIMARY KEY,
    destination VARCHAR(100),
    retail_rate_per_min NUMERIC(8, 4),
    wholesale_cost_per_min NUMERIC(8, 4)
);

CREATE TABLE cdr_usage (
    call_id VARCHAR(50) PRIMARY KEY,
    timestamp TIMESTAMP,
    reseller_id INT,
    destination_number VARCHAR(50),
    destination_prefix VARCHAR(20),
    duration_seconds INT
);

CREATE TABLE supplier_wholesale_bill (
    call_id VARCHAR(50) PRIMARY KEY,
    supplier_billed_charge NUMERIC(10, 4)
);

-- split
-- 2. Rating Logic
CREATE TABLE rated_cdrs AS
SELECT 
    c.call_id,
    c.timestamp,
    c.reseller_id,
    r.reseller_name,
    c.destination_number,
    c.destination_prefix,
    c.duration_seconds,
    CAST(CEIL(c.duration_seconds / 60.0) AS INT) AS billable_minutes,
    rc.destination,
    rc.retail_rate_per_min,
    rc.wholesale_cost_per_min,
    ROUND(CAST(CEIL(c.duration_seconds / 60.0) AS NUMERIC) * rc.retail_rate_per_min, 4) AS calculated_retail_revenue, -- what customer pays
    ROUND(CAST(CEIL(c.duration_seconds / 60.0) AS NUMERIC) * rc.wholesale_cost_per_min, 4) AS calculated_wholesale_cost -- what carrier charges company
FROM cdr_usage c
LEFT JOIN resellers r ON c.reseller_id = r.reseller_id
LEFT JOIN rate_cards rc ON c.destination_prefix = rc.prefix;

-- 3. Carrier Wholesale Reconciliation & Revenue Leakage Audit
CREATE TABLE billing_audit_exceptions AS
SELECT 
    rc.call_id,
    rc.timestamp,
    rc.reseller_id,
    COALESCE(rc.reseller_name, 'UNMAPPED RESELLER') AS reseller_name,
    rc.destination_number,
    rc.billable_minutes,
    rc.calculated_retail_revenue,
    rc.calculated_wholesale_cost,
    s.supplier_billed_charge,
    ROUND(COALESCE(rc.calculated_retail_revenue, 0) - s.supplier_billed_charge, 4) AS net_margin,
    CASE 
        WHEN rc.reseller_name IS NULL 
            THEN 'ERR_UNMAPPED_RESELLER'
        WHEN rc.destination IS NULL 
            THEN 'ERR_MISSING_RATE_CARD'
        WHEN rc.calculated_retail_revenue < s.supplier_billed_charge 
            THEN 'ERR_NEGATIVE_MARGIN'
        WHEN ABS(rc.calculated_wholesale_cost - s.supplier_billed_charge) > 0.05 
            THEN 'ERR_SUPPLIER_OVERBILLING' -- Wholesale carriers frequently make billing errors. The billing/finance team uses automated reconciliation queries like this to audit vendor invoices, catching carrier overbilling before paying out millions in wholesale costs.
        ELSE 'VALID'
    END AS audit_status
FROM rated_cdrs rc
INNER JOIN supplier_wholesale_bill s ON rc.call_id = s.call_id
WHERE 
    rc.reseller_name IS NULL
    OR rc.destination IS NULL
    OR rc.calculated_retail_revenue < s.supplier_billed_charge
    OR ABS(rc.calculated_wholesale_cost - s.supplier_billed_charge) > 0.05;