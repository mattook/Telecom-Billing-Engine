import os
import psycopg2
import pandas as pd

# Adjust connection credentials if required
DB_NAME = os.getenv("PGDATABASE", "billing_db")
DB_USER = os.getenv("PGUSER", "Admin")
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor()

# 1. Read and apply schema
with open("sql/schema_and_reconciliation.sql", "r") as f:
    sql_script = f.read()

# Execute schema creation up to base tables
base_schema = sql_script.split("-- split")[0]
cur.execute(base_schema)
conn.commit()

# 2. Bulk Copy CSVs into PostgreSQL
tables_to_load = [
    ("resellers", "data/resellers.csv"),
    ("rate_cards", "data/rate_cards.csv"),
    ("cdr_usage", "data/cdr_usage.csv"),
    ("supplier_wholesale_bill", "data/supplier_wholesale_bill.csv")
]

for table_name, file_path in tables_to_load:
    with open(file_path, "r") as f:
        cur.copy_expert(
            f"COPY {table_name} FROM STDIN WITH (FORMAT csv, HEADER true)", f)
conn.commit()

# 3. Execute Rating and Exception Logic
transformation_sql = sql_script.split("-- split")[1]
cur.execute(transformation_sql)
conn.commit()

# 4. Fetch Aggregate Metrics
cur.execute("SELECT COUNT(*) FROM rated_cdrs;")
total_cdrs = cur.fetchone()[0]

cur.execute("SELECT COALESCE(SUM(calculated_retail_revenue), 0) FROM rated_cdrs;")
total_revenue = float(cur.fetchone()[0])

cur.execute(
    "SELECT COALESCE(SUM(supplier_billed_charge), 0) FROM supplier_wholesale_bill;")
total_carrier_cost = float(cur.fetchone()[0])

# 5. Extract Exceptions via Pandas
exceptions_df = pd.read_sql("SELECT * FROM billing_audit_exceptions;", conn)
exceptions_df.to_csv("reports/monthly_billing_exceptions.csv", index=False)

# 6. Print Executive Summary
print("=" * 65)
print("REVENUE ASSURANCE AUDIT REPORT (PostgreSQL Engine)")
print("=" * 65)
print(f"Total Call Records Processed:   {total_cdrs}")
print(f"Total Gross Billed:             £{total_revenue:,.2f}")
print(f"Total Carrier Wholesale Cost:   £{total_carrier_cost:,.2f}")
print(
    f"Net Realised Margin:            £{(total_revenue - total_carrier_cost):,.2f}")
print("-" * 65)
print(f"Flagged Exception Records:      {len(exceptions_df)}")
print("\nExceptions Breakdown by Error Type:")
print(exceptions_df["audit_status"].value_counts().to_string())
print("-" * 65)
print("Sample Leakage Records (exported to reports/monthly_billing_exceptions.csv):")
print(exceptions_df[["call_id", "reseller_name", "audit_status", "calculated_retail_revenue",
      "supplier_billed_charge", "net_margin"]].to_string(index=False))
print("=" * 65)

cur.close()
conn.close()
