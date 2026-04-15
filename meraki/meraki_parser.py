"""
Meraki Alert Parser
-------------------
Converts raw Meraki webhook payloads into the NOC agent alert format.

Meraki alert types reference:
https://developer.cisco.com/meraki/webhooks/alert-types/
"""

from datetime import datetime, timezone
import uuid


# Maps Meraki alertType → (NOC Category, Severity)
ALERT_MAP = {
    # Network / Connectivity
    "gateway_to_wan_connectivity":          ("Network",     "Critical"),
    "gateway_connectivity":                 ("Network",     "Critical"),
    "AP_connected":                         ("Network",     "Low"),
    "AP_disconnected":                      ("Network",     "High"),
    "client_connectivity":                  ("Network",     "Medium"),
    "port_connected":                       ("Network",     "Low"),
    "port_disconnected":                    ("Network",     "High"),
    "rogue_ap_detected":                    ("Security",    "High"),
    "ssid_spoofing_detected":               ("Security",    "Critical"),
    "dhcp_no_leases":                       ("Network",     "High"),
    "vlan_connectivity":                    ("Network",     "Medium"),

    # Security
    "ids_alert":                            ("Security",    "Critical"),
    "ARP_CACHE_FLOOD":                      ("Security",    "High"),
    "ARP_SPOOF":                            ("Security",    "Critical"),
    "DHCP_FLOOD":                           ("Security",    "High"),
    "malware_detected":                     ("Security",    "Critical"),
    "intrusion_detected":                   ("Security",    "Critical"),
    "content_filtering_block":              ("Security",    "Medium"),
    "vpn_connectivity_change":              ("Network",     "High"),

    # Hardware
    "power_supply_up":                      ("Hardware",    "Low"),
    "power_supply_down":                    ("Hardware",    "Critical"),
    "temperature_alert":                    ("Hardware",    "High"),
    "cloud_controller_connectivity":        ("Hardware",    "Critical"),
    "device_packet_flood":                  ("Hardware",    "High"),

    # Performance / Application
    "usage_alert":                          ("Application", "Medium"),
    "high_latency":                         ("Network",     "High"),
    "poor_roam":                            ("Application", "Medium"),
    "clients_peak":                         ("Application", "Low"),
}

# Meraki alert types that are informational and should not create tickets
IGNORED_TYPES = {
    "AP_connected",
    "port_connected",
    "power_supply_up",
    "clients_peak",
}


def _get_category_severity(alert_type: str):
    """Look up category and severity for a Meraki alertType."""
    return ALERT_MAP.get(alert_type, ("Network", "Medium"))


def _build_raw_logs(payload: dict) -> str:
    """Construct a readable log string from Meraki payload fields."""
    lines = []
    if payload.get("deviceName"):
        lines.append(f"Device:      {payload['deviceName']}")
    if payload.get("deviceModel"):
        lines.append(f"Model:       {payload['deviceModel']}")
    if payload.get("deviceSerial"):
        lines.append(f"Serial:      {payload['deviceSerial']}")
    if payload.get("networkName"):
        lines.append(f"Network:     {payload['networkName']}")
    if payload.get("organizationName"):
        lines.append(f"Org:         {payload['organizationName']}")
    if payload.get("occurredAt"):
        lines.append(f"Occurred At: {payload['occurredAt']}")

    alert_data = payload.get("alertData", {})
    if alert_data:
        lines.append("Alert Data:")
        for k, v in alert_data.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines) if lines else "No additional log data"


def _build_alert_message(alert_type: str, payload: dict) -> str:
    """Build a human-readable alert message."""
    device = payload.get("deviceName") or payload.get("deviceSerial") or "Unknown Device"
    network = payload.get("networkName", "")
    alert_data = payload.get("alertData", {})

    # Friendly descriptions for common alert types
    descriptions = {
        "gateway_to_wan_connectivity": f"{device} lost WAN connectivity",
        "gateway_connectivity":        f"Gateway {device} is unreachable",
        "AP_disconnected":             f"Access point {device} disconnected from network",
        "port_disconnected":           f"Port disconnected on {device}",
        "ids_alert":                   f"IDS/IPS alert triggered on {device}: {alert_data.get('message', '')}",
        "ARP_CACHE_FLOOD":             f"ARP cache flood detected on {device}",
        "ARP_SPOOF":                   f"ARP spoofing detected on network {network}",
        "DHCP_FLOOD":                  f"DHCP flood attack detected on {device}",
        "malware_detected":            f"Malware detected on {device}: {alert_data.get('name', '')}",
        "intrusion_detected":          f"Network intrusion detected on {device}",
        "rogue_ap_detected":           f"Rogue access point detected on network {network}",
        "ssid_spoofing_detected":      f"SSID spoofing detected — fake SSID: {alert_data.get('ssid', '')}",
        "power_supply_down":           f"Power supply failure on {device}",
        "temperature_alert":           f"Temperature threshold exceeded on {device}: {alert_data.get('temperature', '')}°C",
        "vpn_connectivity_change":     f"VPN connectivity changed on {device}: {alert_data.get('connectivity', '')}",
        "usage_alert":                 f"High usage alert on {device}: {alert_data.get('usage', '')}",
        "high_latency":                f"High latency detected on {device}: {alert_data.get('latency_ms', '')}ms",
        "dhcp_no_leases":              f"DHCP pool exhausted on {device} — no leases available",
        "cloud_controller_connectivity": f"Device {device} lost connection to Meraki cloud",
        "content_filtering_block":     f"Content filtering blocked request on {device}",
    }

    return descriptions.get(alert_type, f"{alert_type.replace('_', ' ').title()} on {device}")


def parse_meraki_alert(payload: dict) -> dict | None:
    """
    Parse a raw Meraki webhook payload into the NOC agent alert format.

    Returns None if the alert is informational and should be ignored.
    Returns a dict with keys: Ticket_ID, Category, Alert_Message, Raw_Logs, Severity, Source, Timestamp
    """
    alert_type = payload.get("alertType", "unknown")

    if alert_type in IGNORED_TYPES:
        return None

    category, severity = _get_category_severity(alert_type)

    ticket_id = f"MRK-{uuid.uuid4().hex[:6].upper()}"
    timestamp = payload.get("occurredAt") or datetime.now(timezone.utc).isoformat()

    return {
        "Ticket_ID":     ticket_id,
        "Category":      category,
        "Alert_Message": _build_alert_message(alert_type, payload),
        "Raw_Logs":      _build_raw_logs(payload),
        "Severity":      severity,
        "Source":        "Cisco Meraki",
        "Timestamp":     timestamp,
    }
