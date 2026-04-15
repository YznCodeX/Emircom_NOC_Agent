"""
Cisco DevNet — DNA Center Alert Connector
-----------------------------------------
Polls the Cisco DNA Center Always-On Sandbox for real network device
health data and generates NOC alerts to feed into the AI agent.

Sandbox: https://sandboxdnac.cisco.com
Credentials: devnetuser / Cisco123!

Run standalone:
    python cisco/devnet_connector.py

Or import:
    from cisco.devnet_connector import get_live_alerts
"""

import requests
import urllib3
import json
import time
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
DNAC_BASE  = "https://sandboxdnac.cisco.com"
DNAC_USER  = "devnetuser"
DNAC_PASS  = "Cisco123!"

# Alert thresholds
CPU_WARN     = 70   # % — warning
CPU_CRIT     = 90   # % — critical
MEM_WARN     = 75   # % — warning
MEM_CRIT     = 90   # % — critical
HEALTH_WARN  = 7    # score /10 — warning (below this = alert)
HEALTH_CRIT  = 4    # score /10 — critical

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_token():
    """Get DNA Center auth token."""
    r = requests.post(
        f"{DNAC_BASE}/dna/system/api/v1/auth/token",
        auth=(DNAC_USER, DNAC_PASS),
        verify=False,
        timeout=15
    )
    r.raise_for_status()
    return r.json()["Token"]


def dnac_get(token, path, params=None):
    """Make a DNA Center API GET call."""
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
    r = requests.get(
        f"{DNAC_BASE}{path}",
        headers=headers,
        params=params,
        verify=False,
        timeout=15
    )
    if r.status_code == 200:
        return r.json().get("response", [])
    return []


# ── Alert Generation ──────────────────────────────────────────────────────────
def analyze_device(device):
    """Analyze a device and return a list of alerts."""
    alerts = []
    name   = device.get("name", "Unknown")
    ip     = device.get("ipAddress", "Unknown")
    model  = device.get("model", "Unknown")
    cpu    = device.get("cpuUtilization", 0) or 0
    mem    = device.get("memoryUtilization", 0) or 0
    health = device.get("overallHealth", 10) or 10
    reach  = device.get("reachabilityHealth", "REACHABLE")
    issues = device.get("issueCount", 0) or 0
    ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Reachability alert ────────────────────────────────────────────────────
    if reach != "REACHABLE":
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-UNREACH-{int(time.time())}",
            "Category":      "Network",
            "Alert_Message": f"Device Unreachable — {name} ({ip})",
            "Raw_Logs":      f"[{ts}] DNA Center reports {name} ({ip}) is {reach}. Model: {model}. Immediate investigation required.",
            "Severity":      "Critical",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })

    # ── CPU alert ─────────────────────────────────────────────────────────────
    if cpu >= CPU_CRIT:
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-CPU-{int(time.time())}",
            "Category":      "Hardware",
            "Alert_Message": f"Critical CPU Utilization on {name} — {cpu:.1f}%",
            "Raw_Logs":      f"[{ts}] DNA Center reports CPU utilization at {cpu:.1f}% on {name} ({ip}). Threshold: {CPU_CRIT}%. Model: {model}. Health score: {health}/10.",
            "Severity":      "Critical",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })
    elif cpu >= CPU_WARN:
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-CPU-{int(time.time())}",
            "Category":      "Hardware",
            "Alert_Message": f"High CPU Utilization on {name} — {cpu:.1f}%",
            "Raw_Logs":      f"[{ts}] DNA Center reports CPU utilization at {cpu:.1f}% on {name} ({ip}). Warning threshold: {CPU_WARN}%. Model: {model}. Health score: {health}/10.",
            "Severity":      "High",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })

    # ── Memory alert ──────────────────────────────────────────────────────────
    if mem >= MEM_CRIT:
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-MEM-{int(time.time())}",
            "Category":      "Hardware",
            "Alert_Message": f"Critical Memory Utilization on {name} — {mem:.1f}%",
            "Raw_Logs":      f"[{ts}] DNA Center reports memory utilization at {mem:.1f}% on {name} ({ip}). Threshold: {MEM_CRIT}%. Model: {model}. Health score: {health}/10.",
            "Severity":      "Critical",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })
    elif mem >= MEM_WARN:
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-MEM-{int(time.time())}",
            "Category":      "Hardware",
            "Alert_Message": f"High Memory Utilization on {name} — {mem:.1f}%",
            "Raw_Logs":      f"[{ts}] DNA Center reports memory utilization at {mem:.1f}% on {name} ({ip}). Warning threshold: {MEM_WARN}%. Model: {model}. Health score: {health}/10.",
            "Severity":      "High",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })

    # ── Health score alert ────────────────────────────────────────────────────
    if health <= HEALTH_CRIT and reach == "REACHABLE":
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-HEALTH-{int(time.time())}",
            "Category":      "Network",
            "Alert_Message": f"Critical Device Health Score — {name} scored {health}/10",
            "Raw_Logs":      f"[{ts}] DNA Center health score for {name} ({ip}) is {health}/10 (critical threshold: {HEALTH_CRIT}). CPU: {cpu:.1f}%, Memory: {mem:.1f}%, Issues: {issues}. Model: {model}.",
            "Severity":      "Critical",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })
    elif health <= HEALTH_WARN and reach == "REACHABLE":
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-HEALTH-{int(time.time())}",
            "Category":      "Network",
            "Alert_Message": f"Degraded Device Health Score — {name} scored {health}/10",
            "Raw_Logs":      f"[{ts}] DNA Center health score for {name} ({ip}) is {health}/10 (warning threshold: {HEALTH_WARN}). CPU: {cpu:.1f}%, Memory: {mem:.1f}%, Issues: {issues}. Model: {model}.",
            "Severity":      "Medium",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })

    # ── Open issues alert ─────────────────────────────────────────────────────
    if issues > 0:
        alerts.append({
            "Ticket_ID":     f"DNAC-{name}-ISSUES-{int(time.time())}",
            "Category":      "Network",
            "Alert_Message": f"DNA Center Reports {issues} Open Issue(s) on {name}",
            "Raw_Logs":      f"[{ts}] Cisco DNA Center has flagged {issues} active issue(s) on {name} ({ip}). Health score: {health}/10. CPU: {cpu:.1f}%, Memory: {mem:.1f}%. Model: {model}. Check DNA Center for details.",
            "Severity":      "High" if issues >= 3 else "Medium",
            "Source":        "Cisco DNA Center",
            "Timestamp":     ts,
        })

    return alerts


# ── Main API ──────────────────────────────────────────────────────────────────
def get_live_alerts():
    """
    Poll DNA Center and return a list of real network alerts.
    Each alert is a dict compatible with mock_tickets.csv format.
    """
    try:
        token   = get_token()
        devices = dnac_get(token, "/dna/intent/api/v1/device-health")

        all_alerts = []
        for device in devices:
            alerts = analyze_device(device)
            all_alerts.extend(alerts)

        return all_alerts

    except Exception as e:
        print(f"[DevNet Connector] Error: {e}")
        return []


def get_device_summary():
    """Return a summary of all devices and their health."""
    try:
        token   = get_token()
        devices = dnac_get(token, "/dna/intent/api/v1/device-health")

        summary = []
        for d in devices:
            summary.append({
                "name":    d.get("name", "Unknown"),
                "ip":      d.get("ipAddress", "Unknown"),
                "model":   d.get("model", "Unknown"),
                "health":  d.get("overallHealth", "?"),
                "cpu":     d.get("cpuUtilization", "?"),
                "memory":  d.get("memoryUtilization", "?"),
                "status":  d.get("reachabilityHealth", "?"),
                "issues":  d.get("issueCount", 0),
            })
        return summary

    except Exception as e:
        print(f"[DevNet Connector] Error: {e}")
        return []


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Cisco DNA Center — Live Network Status")
    print("=" * 60)

    print("\n📡 Device Summary:")
    summary = get_device_summary()
    for d in summary:
        health_icon = "🔴" if d["health"] <= 4 else "🟡" if d["health"] <= 7 else "🟢"
        print(f"  {health_icon} {d['name']:10s} | IP: {d['ip']:15s} | Health: {d['health']:>3}/10 | CPU: {str(d['cpu']):>6}% | Mem: {str(d['memory']):>5}% | Issues: {d['issues']}")

    print("\n🚨 Generated Alerts:")
    alerts = get_live_alerts()
    if alerts:
        for a in alerts:
            print(f"  [{a['Severity']:8s}] {a['Alert_Message']}")
    else:
        print("  ✅ No alerts — all devices healthy")

    print(f"\nTotal alerts: {len(alerts)}")
    print("=" * 60)
