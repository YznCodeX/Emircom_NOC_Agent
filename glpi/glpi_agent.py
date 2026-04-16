"""
GLPI Agent Worker
-----------------
Polls GLPI for new tickets, runs them through the NOC AI agent,
then posts the analysis back to GLPI as a comment, updates priority,
and assigns the ticket to the correct NOC team group.

Run with:
    python glpi_agent.py
"""

import re
import time
import json
import subprocess
import requests
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.agent_graph import app as agent_app

# ── GLPI Config ──────────────────────────────────────────────────────────────
GLPI_BASE    = "http://localhost/api.php/v1"
APP_TOKEN    = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN   = "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"
POLL_INTERVAL = 15  # seconds between checks

# Track which tickets we already processed
processed_ids = set()

PRIORITY_MAP = {
    "Critical": 6,
    "High":     4,
    "Medium":   3,
    "Low":      2,
}

# SLA names in GLPI mapped to severity — populated at startup
SLA_IDS = {}
SLA_NAME_MAP = {
    "Critical": "SLA - Critical",
    "High":     "SLA - High",
    "Medium":   "SLA - Medium",
    "Low":      "SLA - Low",
}

# NOC team names mapped to ticket categories
TEAM_NAMES = {
    "Network":     "NOC Network Team",
    "Security":    "NOC Security Team",
    "Hardware":    "NOC Hardware Team",
    "Cloud":       "NOC Cloud Team",
    "Application": "NOC Application Team",
}

# Populated at startup with GLPI group IDs
GROUP_IDS = {}


def glpi_session():
    """Get a GLPI session token."""
    r = requests.get(f"{GLPI_BASE}/initSession", headers={
        "App-Token": APP_TOKEN,
        "Authorization": f"user_token {USER_TOKEN}"
    }, timeout=10)
    return r.json().get("session_token")


def glpi_headers(session_token):
    return {
        "App-Token": APP_TOKEN,
        "Session-Token": session_token,
        "Content-Type": "application/json",
    }


def load_sla_ids(headers):
    """Fetch SLA IDs from GLPI and map them to severity levels."""
    r = requests.get(f"{GLPI_BASE}/SLA", headers=headers,
                     params={"range": "0-50"}, timeout=10)
    slas = r.json() if isinstance(r.json(), list) else []
    for sla in slas:
        for severity, name in SLA_NAME_MAP.items():
            if sla.get("name") == name:
                SLA_IDS[severity] = sla["id"]
    print(f"  SLA IDs loaded: {SLA_IDS}")


def assign_sla_to_ticket(headers, ticket_id, severity):
    """Assign the correct SLA to a ticket based on severity."""
    sla_id = SLA_IDS.get(severity)
    if not sla_id:
        return
    requests.put(f"{GLPI_BASE}/Ticket/{ticket_id}", headers=headers, json={
        "input": {"slas_id_ttr": sla_id}
    }, timeout=10)


def get_or_create_groups(headers):
    """Ensure all NOC team groups exist in GLPI and store their IDs."""
    r = requests.get(f"{GLPI_BASE}/Group", headers=headers,
                     params={"range": "0-100"}, timeout=10)
    existing = r.json() if isinstance(r.json(), list) else []
    existing_map = {g["name"]: g["id"] for g in existing if isinstance(g, dict)}

    for category, team_name in TEAM_NAMES.items():
        if team_name in existing_map:
            GROUP_IDS[category] = existing_map[team_name]
            print(f"  ✓ Found group '{team_name}' (id={existing_map[team_name]})")
        else:
            resp = requests.post(f"{GLPI_BASE}/Group", headers=headers, json={
                "input": {
                    "name": team_name,
                    "comment": f"Auto-created by NOC Agent — handles {category} incidents",
                    "is_assign": 1,
                }
            }, timeout=10)
            gid = resp.json().get("id")
            if gid:
                GROUP_IDS[category] = gid
                print(f"  ✅ Created group '{team_name}' (id={gid})")
            else:
                print(f"  ⚠️ Could not create group '{team_name}': {resp.text[:100]}")

    return GROUP_IDS


def assign_group_to_ticket(headers, ticket_id, group_id):
    """Assign a GLPI group to a ticket as the responsible team."""
    r = requests.post(f"{GLPI_BASE}/Group_Ticket", headers=headers, json={
        "input": {
            "tickets_id": ticket_id,
            "groups_id": group_id,
            "type": 2,  # 2 = Assigned (responsible for resolution)
        }
    }, timeout=10)
    return r.status_code


def extract_category(ticket):
    """Extract the broad incident category from ticket content or title."""
    content = ticket.get("content", "")

    # First try: explicit 'Category: X' line injected by push_to_glpi.py
    match = re.search(
        r"Category:\s*(Network|Security|Hardware|Cloud|Application)",
        content, re.IGNORECASE
    )
    if match:
        return match.group(1).capitalize()

    # Second try: keyword scan on title
    title = ticket.get("name", "").lower()
    if any(k in title for k in ["ospf", "bgp", "vlan", "interface", "dhcp",
                                  "dns", "bandwidth", "lacp", "stp", "wan"]):
        return "Network"
    if any(k in title for k in ["malware", "attack", "ddos", "brute force",
                                  "ssl", "ransomware", "acl", "firewall",
                                  "unauthorized", "c2", "certificate"]):
        return "Security"
    if any(k in title for k in ["disk", "psu", "memory", "temperature",
                                  "nic", "hardware", "power", "fan", "ecc"]):
        return "Hardware"
    if any(k in title for k in ["aws", "azure", "kubernetes", "k8s",
                                  "ec2", "s3", "cdn", "cloud", "pod"]):
        return "Cloud"
    if any(k in title for k in ["erp", "sap", "api", "database", "mysql",
                                  "replication", "email", "smtp", "gateway",
                                  "memory leak", "billing"]):
        return "Application"

    return "Network"  # safe default


def has_real_ai_comment(headers, ticket_id):
    """Check if ticket already has a successful AI analysis comment."""
    fu = requests.get(f"{GLPI_BASE}/Ticket/{ticket_id}/ITILFollowup",
                      headers=headers, timeout=10).json()
    if not isinstance(fu, list):
        return False
    for f in fu:
        content = f.get("content", "")
        if "AI NOC Agent Analysis" in content:
            return True
    return False


def get_new_tickets(headers):
    """Fetch tickets that need AI analysis:
    - Status = New (1): freshly created tickets
    - Status = Processing (2): manually created tickets (GLPI default)
    In both cases, only pick up tickets with no successful AI comment yet.
    """
    r = requests.get(f"{GLPI_BASE}/Ticket", headers=headers, params={
        "range": "0-50",
        "sort": "id",
        "order": "DESC",
    }, timeout=10)
    tickets = r.json()
    if not isinstance(tickets, list):
        return []

    candidates = [t for t in tickets
                  if t.get("status") in (1, 2)  # New or Processing
                  and t["id"] not in processed_ids]

    # Filter out tickets that already have a real AI analysis
    result = []
    for t in candidates:
        if not has_real_ai_comment(headers, t["id"]):
            result.append(t)
        else:
            processed_ids.add(t["id"])  # already done, skip forever

    return result


def post_comment(headers, ticket_id, comment):
    """Post an AI analysis comment to a GLPI ticket."""
    requests.post(f"{GLPI_BASE}/ITILFollowup", headers=headers, json={
        "input": {
            "items_id": ticket_id,
            "itemtype": "Ticket",
            "content": comment,
            "is_private": 0,
        }
    }, timeout=10)


STATUS_PENDING = 4  # Pending — waiting for engineer review

def update_ticket(headers, ticket_id, priority, status=STATUS_PENDING):
    """Update ticket priority and set status to Pending (awaiting engineer review)."""
    requests.put(f"{GLPI_BASE}/Ticket/{ticket_id}", headers=headers, json={
        "input": {
            "priority": priority,
            "status": status,
        }
    }, timeout=10)


def analyze_ticket(ticket):
    """Run the ticket through the LangGraph agent."""
    ticket_id = f"GLPI-{ticket['id']}"
    description = ticket.get("name", "No title")
    content_raw = ticket.get("content", "")
    content = re.sub(r"<[^>]+>", "", content_raw).strip()
    category = extract_category(ticket)

    config = {"configurable": {"thread_id": ticket_id}}
    inputs = {
        "ticket_id": ticket_id,
        "category":  category,
        "description": description,
        "logs": content or description,
    }

    try:
        agent_app.invoke(inputs, config=config)
        state = agent_app.get_state(config)
        analysis_raw = state.values.get("analysis", "{}")
        analysis = json.loads(
            analysis_raw.replace("```json", "").replace("```", "").strip()
        )
        analysis["_category"] = category  # carry category forward
        return analysis
    except Exception as e:
        return {
            "error": str(e),
            "Severity": "Medium",
            "Recommended_Action": "Manual review required.",
            "_category": category,
        }


def format_comment(analysis):
    """Format the analysis as a readable GLPI comment."""
    if "error" in analysis:
        return "⚠️ AI analysis temporarily unavailable (rate limit or connection issue). The agent will retry this ticket automatically on the next cycle."

    team = TEAM_NAMES.get(analysis.get("_category", ""), "NOC Team")

    return f"""AI NOC Agent Analysis
{'='*40}
Severity: {analysis.get('Severity', 'Unknown')}
Affected Node: {analysis.get('Affected_Node', 'Unknown')}
Categorization: {analysis.get('Categorization', 'Unknown')}
Assigned Team: {team}

Symptom:
{analysis.get('Symptom_Description', 'N/A')}

Root Cause:
{analysis.get('Root_Cause', 'N/A')}

Business Impact:
{analysis.get('Business_Impact', 'N/A')}

Recommended Action:
{analysis.get('Recommended_Action', 'N/A')}

Confidence: {analysis.get('Confidence_Score', 'N/A')}%
{analysis.get('Confidence_Reason', '')}

Analyzed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}""".strip()


def flush_notifications():
    """Trigger GLPI cron inside Docker to flush the email notification queue."""
    try:
        subprocess.run(
            ["docker", "exec", "glpi", "php",
             "/var/www/html/glpi/front/cron.php", "--allow-superuser"],
            timeout=15, capture_output=True
        )
        print("  📧 Notification queue flushed")
    except Exception as e:
        print(f"  ⚠️ Could not flush notifications: {e}")


def run():
    print("GLPI NOC Agent started — polling every", POLL_INTERVAL, "seconds")
    print("=" * 50)

    # ── Startup: ensure NOC team groups and SLAs exist ──────────────────────
    print("\nSetting up NOC team groups and SLAs in GLPI...")
    try:
        session = glpi_session()
        if not session:
            print("  ⚠️ Could not get GLPI session — is Docker running?")
        else:
            hdrs = glpi_headers(session)
            get_or_create_groups(hdrs)
            load_sla_ids(hdrs)
            requests.get(f"{GLPI_BASE}/killSession", headers=hdrs, timeout=5)
            print(f"  Groups ready: {GROUP_IDS}")
    except Exception as e:
        print(f"  ⚠️ Setup skipped: {e}")

    print("\nStarting ticket poll loop...")
    print("=" * 50)

    while True:
        try:
            session = glpi_session()
            headers = glpi_headers(session)

            # If groups weren't set up yet, try again
            if not GROUP_IDS:
                get_or_create_groups(headers)

            new_tickets = get_new_tickets(headers)

            if new_tickets:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(new_tickets)} new ticket(s)")

                for ticket in new_tickets:
                    tid = ticket["id"]
                    name = ticket.get("name", "Unknown")
                    print(f"  → Analyzing ticket #{tid}: {name}")

                    # Run AI analysis
                    analysis = analyze_ticket(ticket)
                    category = analysis.get("_category", "Network")

                    # Post AI comment only for non-Streamlit tickets
                    # [NOC] tickets already have AI analysis in description
                    if not ticket.get("name", "").startswith("[NOC]"):
                        comment = format_comment(analysis)
                        post_comment(headers, tid, comment)

                    # Update priority + set to Pending
                    severity = analysis.get("Severity", "Medium")
                    priority = PRIORITY_MAP.get(severity, 3)
                    update_ticket(headers, tid, priority)

                    # Assign SLA based on severity
                    assign_sla_to_ticket(headers, tid, severity)

                    # Assign to correct NOC team group
                    group_id = GROUP_IDS.get(category)
                    if group_id:
                        status_code = assign_group_to_ticket(headers, tid, group_id)
                        team_name = TEAM_NAMES.get(category, "Unknown")
                        if status_code in (200, 201):
                            print(f"  ✅ Done — priority={severity}, team={team_name}, comment posted")
                        else:
                            print(f"  ⚠️ Done — priority={severity}, team assignment returned {status_code}")
                    else:
                        print(f"  ✅ Done — priority={severity}, no group found for '{category}'")

                    # Mark as processed
                    processed_ids.add(tid)

                # Flush notification queue so emails go out immediately
                flush_notifications()

            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No new tickets", end="\r")

            # Kill session
            requests.get(f"{GLPI_BASE}/killSession", headers=headers, timeout=5)

        except Exception as e:
            print(f"\nError: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
