# UCaaS Billing Pipeline (Rating & Carrier Reconciliation)

A billing engine using **PostgreSQL** and **Python** designed to model monthly billing cycles for UCaaS and telecom channel providers.

## Whats inside?
* **Pipeline:** Bulk ingestion of call logs and wholesale carrier billing files into PostgreSQL.
* **Rating Engine:** Telecom call durations mapped onto existing rates.
* **Revenue Assurance:** Automatic detection and flagging of the following issues:
    - unrated international prefixes
    - supplier overbilling
    - negative margins
    - unmapped accounts.

## How to set up
```bash
pip install -r requirements.txt
python generate_data.py
python run_audit.py