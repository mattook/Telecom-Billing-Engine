import random
from datetime import datetime, timedelta
import pandas as pd

random.seed(42)

# 1. Resellers
resellers = pd.DataFrame([
    {"reseller_id": 101, "reseller_name": "Company A", "tier": "Gold"},
    {"reseller_id": 102, "reseller_name": "Company B", "tier": "Silver"},
    {"reseller_id": 103, "reseller_name": "Company C", "tier": "Platinum"},
])
resellers.to_csv("data/resellers.csv", index=False)

# 2. Rate Cards (Retail charge vs Wholesale cost)
rate_cards = pd.DataFrame([
    {"prefix": "+441", "destination": "UK Landline",
        "retail_rate_per_min": 0.0200, "wholesale_cost_per_min": 0.0080},
    {"prefix": "+447", "destination": "UK Mobile",
        "retail_rate_per_min": 0.0600, "wholesale_cost_per_min": 0.0250},
    {"prefix": "+1", "destination": "USA / Canada",
        "retail_rate_per_min": 0.0400, "wholesale_cost_per_min": 0.0150},
    # ANOMALY 1: Negative Margin (Retail price lower than upstream carrier cost)
    {"prefix": "+44845", "destination": "UK Special Service",
        "retail_rate_per_min": 0.0300, "wholesale_cost_per_min": 0.0700},
])
rate_cards.to_csv("data/rate_cards.csv", index=False)

# 3. Call Detail Records (CDRs)
destinations = [
    ("+44161234567", "+441"),
    ("+447700900123", "+447"),
    ("+12025550143", "+1"),
    ("+44845123456", "+44845"),
    ("+4930123456", "+49"),  # ANOMALY 2: Germany destination missing from rate card
]

start_time = datetime(2026, 9, 1, 8, 0, 0)
cdrs = []
supplier_bills = []

for i in range(1, 201):
    call_id = f"CDR-202609-{i:04d}"
    call_time = start_time + timedelta(minutes=random.randint(1, 40000))
    duration_sec = random.randint(15, 600)

    # ANOMALY 4: Unmapped Reseller
    reseller_id = 999 if i == 50 else random.choice([101, 102, 103])

    dest_number, prefix = random.choices(
        destinations, weights=[0.45, 0.35, 0.10, 0.05, 0.05]
    )[0]

    cdrs.append({
        "call_id": call_id,
        "timestamp": call_time.strftime("%Y-%m-%d %H:%M:%S"),
        "reseller_id": reseller_id,
        "destination_number": dest_number,
        "destination_prefix": prefix,
        "duration_seconds": duration_sec
    })

    # Telecom rating standard: Round up seconds to next full minute (ceiling)
    billable_mins = duration_sec // 60
    matched_rate = rate_cards[rate_cards["prefix"] == prefix]

    wholesale_rate = matched_rate.iloc[0]["wholesale_cost_per_min"] if not matched_rate.empty else 0.05
    actual_wholesale_charge = round(billable_mins * wholesale_rate, 4)

    # ANOMALY 3: Upstream Carrier Overbilling
    if i in [25, 75]:
        actual_wholesale_charge += 12.50

    supplier_bills.append({
        "call_id": call_id,
        "supplier_billed_charge": actual_wholesale_charge
    })

pd.DataFrame(cdrs).to_csv("data/cdr_usage.csv", index=False)
pd.DataFrame(supplier_bills).to_csv(
    "data/supplier_wholesale_bill.csv", index=False)

print("Generated synthetic CSV files in /data")
