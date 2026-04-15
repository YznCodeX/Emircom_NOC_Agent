"""
Push mock tickets to GLPI
Run: python push_to_glpi.py
"""

import pandas as pd
import requests
import time

GLPI_BASE  = "http://localhost/api.php/v1"
APP_TOKEN  = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN = "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"

PRIORITY_MAP = {"Critical": 6, "High": 4, "Medium": 3, "Low": 2}

def get_session():
    r = requests.get(f"{GLPI_BASE}/initSession", headers={
        "App-Token": APP_TOKEN,
        "Authorization": f"user_token {USER_TOKEN}"
    }, timeout=10)
    return r.json()["session_token"]

def create_ticket(headers, row):
    payload = {
        "input": {
            "name": row["Alert_Message"],
            "content": f"Source: {row['Source']}\nCategory: {row['Category']}\nSeverity: {row['Severity']}\n\nLogs:\n{row['Raw_Logs']}",
            "priority": PRIORITY_MAP.get(row["Severity"], 3),
            "urgency": PRIORITY_MAP.get(row["Severity"], 3),
            "impact": PRIORITY_MAP.get(row["Severity"], 3),
            "type": 1,    # Incident
            "status": 1,  # New — so agent picks it up
        }
    }
    r = requests.post(f"{GLPI_BASE}/Ticket", headers=headers, json=payload, timeout=10)
    return r.json().get("id")

def main():
    df = pd.read_csv("data/mock_tickets.csv")
    print(f"Pushing {len(df)} tickets to GLPI...")

    session = get_session()
    headers = {
        "App-Token": APP_TOKEN,
        "Session-Token": session,
        "Content-Type": "application/json",
    }

    success = 0
    for _, row in df.iterrows():
        tid = create_ticket(headers, row)
        if tid:
            print(f"  ✅ Created GLPI #{tid} — {row['Alert_Message'][:60]}")
            success += 1
        else:
            print(f"  ❌ Failed — {row['Alert_Message'][:60]}")
        time.sleep(0.3)  # don't hammer the API

    requests.get(f"{GLPI_BASE}/killSession", headers=headers, timeout=5)
    print(f"\nDone — {success}/{len(df)} tickets created in GLPI")

if __name__ == "__main__":
    main()
