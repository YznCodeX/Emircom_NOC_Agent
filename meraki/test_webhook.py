"""
Simulate a Meraki webhook alert hitting your local receiver.
Run: python meraki/test_webhook.py
"""
import requests
import json

RECEIVER_URL = "http://localhost:8003/webhook/meraki"

alerts = [
    {
        "alertType": "gateway_to_wan_connectivity",
        "deviceName": "MX-HQ-Firewall",
        "deviceModel": "MX68",
        "deviceSerial": "Q2KN-XXXX-0001",
        "networkName": "Emircom-HQ",
        "organizationName": "Emircom",
        "occurredAt": "2026-04-13T10:22:00Z",
        "alertData": {"connectivity": "lost"}
    },
    {
        "alertType": "ARP_SPOOF",
        "deviceName": "MS-Core-SW1",
        "deviceModel": "MS250",
        "deviceSerial": "Q2HP-YYYY-0002",
        "networkName": "Emircom-DC",
        "organizationName": "Emircom",
        "occurredAt": "2026-04-13T10:25:00Z",
        "alertData": {}
    },
    {
        "alertType": "AP_disconnected",
        "deviceName": "MR-Floor3-AP2",
        "deviceModel": "MR46",
        "deviceSerial": "Q2LD-ZZZZ-0003",
        "networkName": "Emircom-Office",
        "organizationName": "Emircom",
        "occurredAt": "2026-04-13T10:30:00Z",
        "alertData": {}
    },
]

for alert in alerts:
    print(f"\n→ Sending: {alert['alertType']} on {alert['deviceName']}")
    try:
        r = requests.post(RECEIVER_URL, json=alert, timeout=60)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {json.dumps(r.json(), indent=2)}")
    except Exception as e:
        print(f"  Error: {e}")
