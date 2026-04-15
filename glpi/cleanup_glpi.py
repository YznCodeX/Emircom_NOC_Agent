"""
GLPI Cleanup Script
Deletes all tickets from GLPI so we can start fresh.
Run: python glpi/cleanup_glpi.py
"""

import requests
import sys

GLPI_BASE  = "http://localhost/api.php/v1"
APP_TOKEN  = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN = "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"


def glpi_session():
    r = requests.get(f"{GLPI_BASE}/initSession", headers={
        "App-Token": APP_TOKEN,
        "Authorization": f"user_token {USER_TOKEN}"
    }, timeout=10)
    return r.json().get("session_token")


def glpi_headers(token):
    return {
        "App-Token": APP_TOKEN,
        "Session-Token": token,
        "Content-Type": "application/json"
    }


def get_all_ticket_ids(headers):
    ids = []
    range_start = 0
    range_size = 50
    while True:
        r = requests.get(f"{GLPI_BASE}/Ticket", headers=headers, params={
            "range": f"{range_start}-{range_start + range_size - 1}",
            "only_id": True,
        }, timeout=10)
        if r.status_code == 206 or r.status_code == 200:
            batch = r.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break
            ids.extend([t["id"] for t in batch])
            if len(batch) < range_size:
                break
            range_start += range_size
        else:
            break
    return ids


def delete_ticket(ticket_id, headers):
    r = requests.delete(
        f"{GLPI_BASE}/Ticket/{ticket_id}",
        headers=headers,
        json={"input": {"id": ticket_id}, "force_purge": True},
        timeout=10
    )
    return r.status_code in [200, 204]


def main():
    print("Connecting to GLPI...")
    session = glpi_session()
    if not session:
        print("ERROR: Could not connect to GLPI. Is Docker running?")
        sys.exit(1)

    headers = glpi_headers(session)

    print("Fetching all ticket IDs...")
    ids = get_all_ticket_ids(headers)
    total = len(ids)

    if total == 0:
        print("No tickets found — GLPI is already clean.")
        return

    print(f"Found {total} tickets to delete.")
    confirm = input(f"Delete all {total} tickets? This cannot be undone. Type YES to confirm: ")

    if confirm.strip() != "YES":
        print("Cancelled.")
        return

    print("Deleting...")
    success = 0
    failed = 0
    for i, tid in enumerate(ids, 1):
        ok = delete_ticket(tid, headers)
        if ok:
            success += 1
            print(f"  [{i}/{total}] Deleted ticket #{tid}")
        else:
            failed += 1
            print(f"  [{i}/{total}] FAILED to delete ticket #{tid}")

    requests.get(f"{GLPI_BASE}/killSession", headers=headers, timeout=5)

    print(f"\nDone. Deleted: {success} | Failed: {failed}")
    print("GLPI is now clean. Only real approved tickets will appear going forward.")


if __name__ == "__main__":
    main()
