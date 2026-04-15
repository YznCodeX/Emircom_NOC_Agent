"""
Emircom NOC — Realistic Mock Data Generator
Generates telecom-grade NOC alerts with proper syslog format,
device variety, and realistic severity distribution.
"""

import pandas as pd
import random
import os
from datetime import datetime, timedelta

# ── Device inventory (Emircom-style naming) ──────────────────────────────────
NETWORK_DEVICES = [
    "Core-RTR-RUH-01", "Core-RTR-RUH-02", "Core-RTR-JED-01",
    "PE-RTR-JED-02", "PE-RTR-MED-01", "AGG-SW-RUH-03",
    "Core-SW-RUH-01", "Core-SW-JED-01", "Dist-SW-MED-02",
    "FW-FortiGate-RUH-01", "FW-FortiGate-JED-01",
    "BNG-01-RUH", "BNG-02-JED", "BRAS-RUH-01",
]

HARDWARE_DEVICES = [
    "Server-ESX-01", "Server-ESX-02", "Server-ESX-03",
    "Server-DB-01", "Server-DB-02", "Server-APP-01",
    "Storage-SAN-01", "Storage-SAN-02",
    "Switch-Core-RUH-01", "Switch-Core-JED-01",
    "UPS-DataCenter-RUH-A", "PDU-Rack-07-RUH",
]

CLOUD_RESOURCES = [
    "prod-api-server", "prod-auth-service", "prod-billing-svc",
    "staging-api-01", "prod-sqldb-01", "prod-sqldb-02",
    "payment-service", "notification-service", "crm-backend",
    "emircom-backup-prod", "emircom-logs-archive",
]

APP_SERVICES = [
    "api.emircom.net", "portal.emircom.net", "billing.emircom.net",
    "SAP-PROD-01", "CRM-PROD-01", "SMTP-GW-01", "SMTP-GW-02",
    "MySQL-REPLICA-01", "MySQL-REPLICA-02", "MongoDB-PROD-01",
    "billing-service", "auth-service", "reporting-service",
]

TELECOM_NODES = [
    "eNB-RUH-Tower-047", "eNB-JED-Tower-112", "eNB-MED-Tower-033",
    "gNB-RUH-5G-001", "gNB-JED-5G-004",
    "MSC-RUH-01", "HLR-CORE-01", "SGSN-JED-01",
    "PGW-CORE-01", "SGW-RUH-01", "IMS-CSCF-01",
]

INTERFACES = [
    "GigabitEthernet0/0", "GigabitEthernet0/1", "GigabitEthernet1/0",
    "TenGigabitEthernet0/1", "TenGigabitEthernet1/2",
    "Bundle-Ether10", "Bundle-Ether20",
    "Serial0/0/0", "Serial0/1/0",
]

BGP_PEERS = [
    "10.1.1.2", "10.1.1.6", "172.16.0.1", "172.16.10.1",
    "192.168.100.1", "10.255.0.1",
]

ATTACKER_IPS = [
    "185.220.101.45", "91.108.4.22", "45.33.32.156",
    "194.165.16.11", "103.75.190.5", "5.188.206.26",
]

INTERNAL_IPS = [
    "10.0.5.22", "10.10.1.45", "172.16.5.100",
    "10.0.8.77", "192.168.50.12",
]

def ts():
    """Random syslog-style timestamp."""
    months = ["Jan", "Feb", "Mar", "Apr"]
    day = random.randint(1, 28)
    h = random.randint(0, 23)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"Apr {day:02d} {h:02d}:{m:02d}:{s:02d}"


# ── Alert templates ───────────────────────────────────────────────────────────

def network_alerts():
    dev = random.choice(NETWORK_DEVICES)
    iface = random.choice(INTERFACES)
    peer = random.choice(BGP_PEERS)
    bw = random.randint(85, 99)
    cpu = random.randint(88, 98)

    return random.choice([
        {
            "alert": f"BGP Session Down on {dev} — Peer {peer}",
            "log": (
                f"{ts()} {dev} BGP[1234]: %BGP-5-ADJCHANGE: neighbor {peer} Down "
                f"BGP Notification sent, error code Cease (subcode peer de-configured)\n"
                f"{ts()} {dev} BGP[1234]: %BGP-3-NOTIFICATION: sent to neighbor {peer} "
                f"6/3 (cease/peer unconfigured) 0 bytes\n"
                f"{ts()} {dev} BGP[1234]: %BGP-5-ADJCHANGE: neighbor {peer} Down Interface flap"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"OSPF Neighbor Down on {dev}",
            "log": (
                f"{ts()} {dev} OSPF[100]: %OSPF-5-ADJCHG: Process 1, Nbr {peer} on "
                f"{iface} from FULL to DOWN, Neighbor Down: Dead timer expired\n"
                f"{ts()} {dev} OSPF[100]: %OSPF-4-ERRRCV: Received invalid packet: "
                f"mismatched area ID from backbone area from {peer}, {iface}\n"
                f"{ts()} {dev} OSPF[100]: Interface {iface} going down"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"WAN Link Saturation on {dev} — {iface} at {bw}%",
            "log": (
                f"{ts()} {dev} ifmgr[145]: Interface {iface}: output rate {bw*1000000} bits/sec, "
                f"input rate {int(bw*0.6)*1000000} bits/sec, {bw}% bandwidth utilization\n"
                f"{ts()} {dev} QOS[200]: CBWFQ: Queue drops on class VOICE: 1250 packets\n"
                f"{ts()} {dev} QOS[200]: Traffic-shape avg rate exceeded on {iface}: "
                f"CIR=100Mbps, current={bw}Mbps"
            ),
            "severity": "High",
        },
        {
            "alert": f"High CPU on {dev} — {cpu}% for 10 minutes",
            "log": (
                f"{ts()} {dev} kernel: CPU utilization for five seconds: {cpu}%/12%; "
                f"one minute: {cpu-3}%; five minutes: {cpu-5}%\n"
                f"{ts()} {dev} kernel: Process BGP consuming 34% CPU cycles\n"
                f"{ts()} {dev} kernel: IP Input process: 28% — possible route flap or ACL storm"
            ),
            "severity": "High",
        },
        {
            "alert": f"Interface {iface} Down on {dev}",
            "log": (
                f"{ts()} {dev} ifmgr[145]: %LINK-3-UPDOWN: Interface {iface}, changed state to down\n"
                f"{ts()} {dev} ifmgr[145]: %LINEPROTO-5-UPDOWN: Line protocol on Interface "
                f"{iface}, changed state to down\n"
                f"{ts()} {dev} chassis[500]: Physical layer alarm on {iface}: "
                f"Loss of signal detected, check fiber/cable"
            ),
            "severity": "High",
        },
        {
            "alert": f"DHCP Pool Exhausted on {dev} — VLAN {random.randint(10,100)}",
            "log": (
                f"{ts()} {dev} dhcpd[88]: DHCP pool VLAN{random.randint(10,100)} exhausted, "
                f"no available IP addresses, 254/254 leases active\n"
                f"{ts()} {dev} dhcpd[88]: DHCPDISCOVER from 00:1A:2B:3C:4D:5E via {iface}: "
                f"no free leases\n"
                f"{ts()} {dev} dhcpd[88]: Lease renewal rate 98% — pool near exhaustion for 15 minutes"
            ),
            "severity": "High",
        },
        {
            "alert": f"MPLS LDP Session Down on {dev} — Peer {peer}",
            "log": (
                f"{ts()} {dev} LDP[300]: %LDP-5-NBRCHG: LDP Neighbor {peer}:0 is DOWN "
                f"(TCP connection closed)\n"
                f"{ts()} {dev} LDP[300]: %LDP-3-SESSION_PROT: "
                f"Session {peer}:0 - TCP keepalive timeout\n"
                f"{ts()} {dev} LDP[300]: MPLS forwarding table inconsistency — "
                f"label bindings withdrawn for 48 prefixes"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Port Flapping on {dev} — {iface}",
            "log": (
                f"{ts()} {dev} ifmgr[145]: %LINK-3-UPDOWN: Interface {iface}, changed state to down\n"
                f"{ts()} {dev} ifmgr[145]: %LINK-3-UPDOWN: Interface {iface}, changed state to up\n"
                f"{ts()} {dev} ifmgr[145]: %LINK-3-UPDOWN: Interface {iface}, changed state to down\n"
                f"{ts()} {dev} ifmgr[145]: Interface {iface} flapped 14 times in 60 seconds — "
                f"err-disable triggered. Check SFP module or cable."
            ),
            "severity": "Medium",
        },
        {
            "alert": f"DNS Resolution Failure on {dev}",
            "log": (
                f"{ts()} {dev} named[512]: DNS query timeout for domain internal.emircom.net "
                f"from 10.0.0.5, retries exhausted\n"
                f"{ts()} {dev} named[512]: SERVFAIL response from upstream 8.8.8.8 — "
                f"recursion failed\n"
                f"{ts()} {dev} named[512]: Zone transfer for emircom.net failed: "
                f"connection refused from primary 10.0.1.1"
            ),
            "severity": "Medium",
        },
        {
            "alert": f"Cell Tower eNB Down — {random.choice(TELECOM_NODES)}",
            "log": (
                f"{ts()} {random.choice(TELECOM_NODES)} enb-mgr[77]: "
                f"S1-AP link to MME lost — eNB out of service\n"
                f"{ts()} {random.choice(TELECOM_NODES)} enb-mgr[77]: "
                f"X2 interface to neighbor eNB timeout — handover failure risk\n"
                f"{ts()} {random.choice(TELECOM_NODES)} enb-mgr[77]: "
                f"Alarm: TX power anomaly detected — check antenna feed cable"
            ),
            "severity": "Critical",
        },
    ])


def security_alerts():
    attacker = random.choice(ATTACKER_IPS)
    internal = random.choice(INTERNAL_IPS)
    dev = random.choice(NETWORK_DEVICES)
    count = random.randint(300, 600)
    pps = random.randint(200000, 600000)

    return random.choice([
        {
            "alert": f"Brute Force SSH Attack from {attacker} on {dev}",
            "log": (
                f"{ts()} {dev} sshd[4421]: Failed password for root from {attacker} port "
                f"{random.randint(40000,65000)} ssh2\n"
                f"{ts()} {dev} sshd[4421]: Failed password for admin from {attacker} port "
                f"{random.randint(40000,65000)} ssh2\n"
                f"{ts()} {dev} sshd[4421]: {count} failed login attempts in 60 seconds from "
                f"{attacker} — IPS block rule applied\n"
                f"{ts()} {dev} IPS[100]: Signature SSH_BRUTE_FORCE triggered: "
                f"src={attacker}, dst={dev}, action=drop"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"DDoS SYN Flood on Public IP — {pps} pps",
            "log": (
                f"{ts()} {dev} DDoS-Guard[55]: SYN flood detected: {pps} packets/sec "
                f"from {random.randint(100,300)} source IPs\n"
                f"{ts()} {dev} DDoS-Guard[55]: Traffic scrubbing center activated — "
                f"mitigation in progress\n"
                f"{ts()} {dev} DDoS-Guard[55]: Top source: {attacker} — {int(pps*0.15)} pps\n"
                f"{ts()} {dev} FortiDDOS[22]: Rate-limit applied on upstream interface: "
                f"SYN cookie enabled"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Malware C2 Communication from Internal Host {internal}",
            "log": (
                f"{ts()} {dev} IPS[100]: Malware CnC Communication detected\n"
                f"  Src: {internal}:{random.randint(1024,65000)}\n"
                f"  Dst: {attacker}:443\n"
                f"  Signature: Emotet.C2.TCP (CVE-2023-1234)\n"
                f"{ts()} {dev} FortiSIEM[300]: Host {internal} beaconing every 30s — "
                f"C2 pattern confirmed\n"
                f"{ts()} {dev} EDR[500]: Process: svchost.exe (PID 4821) — suspicious "
                f"outbound connection to known malicious IP"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Ransomware Activity Detected on Internal Host {internal}",
            "log": (
                f"{ts()} {dev} EDR[500]: Mass file encryption detected on host {internal}\n"
                f"{ts()} {dev} EDR[500]: {random.randint(1500,3000)} files encrypted in 30 seconds, "
                f"extension: .locked\n"
                f"{ts()} {dev} EDR[500]: Malicious process: svchost.exe (PID {random.randint(3000,8000)}) "
                f"— process terminated, host isolated\n"
                f"{ts()} {dev} FortiSIEM[300]: MITRE ATT&CK T1486 — Data Encrypted for Impact"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Unauthorized Admin Login on {dev} — {random.randint(20,50)} Failed Attempts",
            "log": (
                f"{ts()} {dev} auth[200]: Admin login failed from IP {internal} via HTTPS\n"
                f"{ts()} {dev} auth[200]: Username: admin — wrong password "
                f"({random.randint(20,50)} attempts in 5 minutes)\n"
                f"{ts()} {dev} auth[200]: Account locked for 30 minutes — lockout policy enforced\n"
                f"{ts()} {dev} FortiSIEM[300]: Correlated with lateral movement from {attacker}"
            ),
            "severity": "High",
        },
        {
            "alert": f"SSL Certificate Expired on portal.emircom.net",
            "log": (
                f"{ts()} portal-lb-01 nginx[112]: SSL handshake failed: certificate expired\n"
                f"{ts()} portal-lb-01 nginx[112]: CN=portal.emircom.net, "
                f"expired: 2026-03-15, issuer: DigiCert Global CA\n"
                f"{ts()} portal-lb-01 nginx[112]: Clients receiving SSL_ERROR_RX_RECORD_TOO_LONG\n"
                f"{ts()} portal-lb-01 nginx[112]: HTTPS traffic failing — "
                f"HTTP fallback active, data exposed"
            ),
            "severity": "High",
        },
        {
            "alert": f"BGP Route Leak — Unauthorized Prefix from {random.choice(BGP_PEERS)}",
            "log": (
                f"{ts()} {dev} BGP[1234]: SECURITY ALERT: Unexpected prefix 0.0.0.0/0 received "
                f"from peer {random.choice(BGP_PEERS)}\n"
                f"{ts()} {dev} BGP[1234]: Prefix-list INBOUND_FILTER: 12 unauthorized prefixes "
                f"accepted — policy violation\n"
                f"{ts()} {dev} BGP[1234]: Traffic rerouting detected — possible BGP hijack\n"
                f"{ts()} {dev} BGP[1234]: NOC ALERT: Contact upstream provider immediately"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"ACL Deny Storm on {dev} — {random.randint(10000,20000)} Blocks/min",
            "log": (
                f"{ts()} {dev} ACL[88]: %SEC-6-IPACCESSLOGP: list ACL_INBOUND denied tcp "
                f"{internal}(1024) -> 192.168.1.1(445), {random.randint(10000,20000)} packets in 60 seconds\n"
                f"{ts()} {dev} ACL[88]: %SEC-6-IPACCESSLOGP: list ACL_INBOUND denied udp "
                f"{internal}(53) -> 8.8.8.8(53)\n"
                f"{ts()} {dev} ACL[88]: Deny storm threshold exceeded — check for worm/scanner"
            ),
            "severity": "High",
        },
    ])


def hardware_alerts():
    dev = random.choice(HARDWARE_DEVICES)
    temp = random.randint(76, 90)
    err_count = random.randint(200, 800)

    return random.choice([
        {
            "alert": f"Disk Failure on {dev} — RAID Degraded",
            "log": (
                f"{ts()} {dev} raid-ctrl[44]: Physical disk failure in enclosure 0, "
                f"slot {random.randint(1,8)}, disk S/N: WD-{random.randint(100000,999999)}\n"
                f"{ts()} {dev} raid-ctrl[44]: RAID-5 array degraded — "
                f"rebuild initiated on hot spare disk\n"
                f"{ts()} {dev} raid-ctrl[44]: Estimated rebuild time: 4h 30m — "
                f"system running in degraded mode\n"
                f"{ts()} {dev} iLO[10]: Hardware alert: replace failed disk immediately"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"High Temperature on {dev} — {temp}°C",
            "log": (
                f"{ts()} {dev} iLO[10]: Inlet temperature {temp}°C — "
                f"threshold 75°C exceeded\n"
                f"{ts()} {dev} iLO[10]: Fan speed at 100% — cooling insufficient\n"
                f"{ts()} {dev} iLO[10]: Risk of thermal throttling in 10 minutes\n"
                f"{ts()} {dev} IPMI[20]: Ambient temp sensor: {temp}°C, "
                f"CPU temp: {temp+12}°C — check CRAC unit in rack zone B"
            ),
            "severity": "High",
        },
        {
            "alert": f"Memory ECC Error on {dev} — {err_count} Errors/Hour",
            "log": (
                f"{ts()} {dev} kernel[1]: Hardware error: Correctable ECC memory error on "
                f"DIMM slot {random.choice(['A1','A2','B1','B2','C1'])}\n"
                f"{ts()} {dev} kernel[1]: Error count: {err_count} in last hour — "
                f"threshold 100/hour exceeded\n"
                f"{ts()} {dev} mcelog[33]: Machine check exception: "
                f"Memory bank 1, rank 0 — replace DIMM recommended\n"
                f"{ts()} {dev} iLO[10]: IML entry: Corrected Memory Error rate exceeded"
            ),
            "severity": "Medium",
        },
        {
            "alert": f"PSU Failure on {dev} — PSU-{random.randint(1,2)}",
            "log": (
                f"{ts()} {dev} iLO[10]: Power supply {random.randint(1,2)} failure detected\n"
                f"{ts()} {dev} iLO[10]: Input voltage: 0V (expected 220V AC) — "
                f"PSU offline\n"
                f"{ts()} {dev} iLO[10]: Redundant PSU active — single point of failure now\n"
                f"{ts()} {dev} IPMI[20]: PS Status: FAILURE — "
                f"open service ticket for PSU replacement"
            ),
            "severity": "High",
        },
        {
            "alert": f"NIC Failure on {dev} — eth{random.randint(0,3)}",
            "log": (
                f"{ts()} {dev} kernel[1]: Network interface eth{random.randint(0,3)} "
                f"link failure detected\n"
                f"{ts()} {dev} kernel[1]: ethtool: Link is Down — "
                f"auto-negotiation failed\n"
                f"{ts()} {dev} bonding[55]: Failover to eth{random.randint(0,3)} complete — "
                f"bond0 operating on single link\n"
                f"{ts()} {dev} iLO[10]: NIC teaming degraded — investigate NIC or cable on failed port"
            ),
            "severity": "High",
        },
        {
            "alert": f"UPS Battery Low on {random.choice(['UPS-DataCenter-RUH-A','UPS-DataCenter-JED-B'])}",
            "log": (
                f"{ts()} ups-mgr[77]: UPS battery capacity: {random.randint(8,20)}% — "
                f"critical threshold 20% breached\n"
                f"{ts()} ups-mgr[77]: Estimated runtime on battery: {random.randint(3,8)} minutes\n"
                f"{ts()} ups-mgr[77]: Mains power input: FAILED — "
                f"running on battery since {random.randint(5,20)} minutes\n"
                f"{ts()} ups-mgr[77]: ALERT: Initiate graceful shutdown of non-critical systems"
            ),
            "severity": "Critical",
        },
    ])


def cloud_alerts():
    res = random.choice(CLOUD_RESOURCES)
    cpu = random.randint(90, 99)
    conn = random.randint(450, 500)
    mem_mb = random.choice([512, 1024, 2048])

    return random.choice([
        {
            "alert": f"EC2 Instance High CPU — {res} at {cpu}%",
            "log": (
                f"{ts()} CloudWatch: EC2 instance i-0{random.randint(100000,999999):x} ({res}) "
                f"CPU utilization {cpu}% for 15 minutes\n"
                f"{ts()} CloudWatch: Auto-scaling triggered — "
                f"{random.randint(2,4)} new instances launching in us-east-1a\n"
                f"{ts()} CloudWatch: ELB TargetGroup healthy hosts: "
                f"{random.randint(1,3)}/5 — unhealthy instances being replaced\n"
                f"{ts()} CloudWatch: P99 latency: {random.randint(3000,8000)}ms — SLA breach risk"
            ),
            "severity": "High",
        },
        {
            "alert": f"Database Connection Pool Exhausted — {res}",
            "log": (
                f"{ts()} Azure Monitor: SQL Database {res} connection pool "
                f"at 100% capacity ({conn}/{conn})\n"
                f"{ts()} Azure Monitor: New connections queuing — "
                f"wait time: {random.randint(5000,12000)}ms\n"
                f"{ts()} Azure Monitor: Query timeout rate: {random.randint(30,60)}% — "
                f"application errors increasing\n"
                f"{ts()} Azure Monitor: DTU consumption: 100% — "
                f"scale up or optimize connection pooling"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Kubernetes Pod CrashLoopBackOff — {res}",
            "log": (
                f"{ts()} k8s-event: Pod {res}-{random.randint(1000,9999)}x in namespace "
                f"production is in CrashLoopBackOff\n"
                f"{ts()} k8s-event: Exit code 137 (OOMKilled) — "
                f"memory limit {mem_mb}Mi exceeded\n"
                f"{ts()} k8s-event: Restart count: {random.randint(10,30)} — "
                f"back-off 5m0s\n"
                f"{ts()} k8s-event: Node pressure: MemoryPressure=True on node worker-02"
            ),
            "severity": "High",
        },
        {
            "alert": f"S3 Bucket Public Access Detected — emircom-backup-prod",
            "log": (
                f"{ts()} AWS Config: S3 bucket emircom-backup-prod ACL changed to public-read\n"
                f"{ts()} AWS Config: Change made by IAM user devops-temp "
                f"(last login: {random.randint(1,7)} days ago)\n"
                f"{ts()} AWS Config: {random.uniform(1.5,3.5):.1f}TB sensitive data potentially exposed\n"
                f"{ts()} AWS GuardDuty: S3 bucket policy allows unauthenticated access — "
                f"remediate immediately"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"CDN Cache Hit Rate Dropped — {random.randint(8,18)}%",
            "log": (
                f"{ts()} Cloudflare: Cache hit rate dropped from 85% to "
                f"{random.randint(8,18)}% in last 30 minutes\n"
                f"{ts()} Cloudflare: Origin server receiving {random.randint(8,15)}x normal traffic\n"
                f"{ts()} Cloudflare: Edge latency: {random.randint(2500,5000)}ms "
                f"(baseline: 120ms)\n"
                f"{ts()} Cloudflare: Cache-Control headers missing on "
                f"{random.randint(40,80)}% of responses — check app config"
            ),
            "severity": "Medium",
        },
        {
            "alert": f"Azure VM Unreachable — {res}",
            "log": (
                f"{ts()} Azure Monitor: VM {res} heartbeat lost — "
                f"last heartbeat {random.randint(5,20)} minutes ago\n"
                f"{ts()} Azure Monitor: Health probe failing on LoadBalancer backend pool\n"
                f"{ts()} Azure Monitor: NSG flow logs: inbound traffic blocked — "
                f"check NSG rules\n"
                f"{ts()} Azure Monitor: Boot diagnostics: OS not responding — "
                f"kernel panic suspected"
            ),
            "severity": "Critical",
        },
    ])


def application_alerts():
    svc = random.choice(APP_SERVICES)
    latency = random.randint(15000, 60000)
    err_rate = random.randint(35, 65)
    queue = random.randint(30000, 80000)

    return random.choice([
        {
            "alert": f"API Gateway High Error Rate — {svc} {err_rate}% 502s",
            "log": (
                f"{ts()} nginx[112]: upstream server returned 502 Bad Gateway — "
                f"error rate {err_rate}%\n"
                f"{ts()} nginx[112]: Upstream pool: {random.randint(2,4)}/5 servers unhealthy, "
                f"health check failing\n"
                f"{ts()} nginx[112]: Active connections: {random.randint(3000,8000)} — "
                f"worker processes at capacity\n"
                f"{ts()} nginx[112]: P99 latency: {random.randint(8000,15000)}ms — "
                f"upstream timeout 30s exceeded"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"ERP Slow Response — {svc} at {latency//1000}s",
            "log": (
                f"{ts()} dynatrace-apm: SAP ERP average response time "
                f"{latency}ms (baseline: 800ms)\n"
                f"{ts()} dynatrace-apm: Root cause: database query timeout on "
                f"table VBAK — {random.randint(5,15)}M rows full scan\n"
                f"{ts()} dynatrace-apm: {random.randint(150,300)} active users affected\n"
                f"{ts()} dynatrace-apm: Missing index on VBAK.ERDAT — "
                f"DB team notified"
            ),
            "severity": "Critical",
        },
        {
            "alert": f"Email Gateway Backlog — {svc}: {queue} Messages",
            "log": (
                f"{ts()} postfix[512]: deferred queue: {queue} messages pending delivery\n"
                f"{ts()} postfix[512]: MX record resolution failed for emircom.net — "
                f"DNS propagation issue\n"
                f"{ts()} postfix[512]: Bounce rate: {random.randint(25,45)}% — "
                f"hard bounces increasing\n"
                f"{ts()} postfix[512]: SMTP relay {random.choice(['10.0.1.20','10.0.1.21'])} "
                f"refusing connections: 421 Too many concurrent connections"
            ),
            "severity": "High",
        },
        {
            "alert": f"Database Replication Lag — {svc}: {random.randint(30,90)} minutes behind",
            "log": (
                f"{ts()} mysql[3306]: Slave_IO_Running: Yes, Slave_SQL_Running: Yes\n"
                f"{ts()} mysql[3306]: Seconds_Behind_Master: {random.randint(1800,5400)}\n"
                f"{ts()} mysql[3306]: Large transaction detected: "
                f"binlog pos {random.randint(100000,999999)} — DDL operation running\n"
                f"{ts()} mysql[3306]: Replication lag increasing — "
                f"read queries on replica returning stale data"
            ),
            "severity": "High",
        },
        {
            "alert": f"Memory Leak Detected — {svc}",
            "log": (
                f"{ts()} jvm[java]: Heap usage: {random.randint(92,98)}% "
                f"({random.randint(7,8)}GB/{random.randint(8,10)}GB)\n"
                f"{ts()} jvm[java]: GC overhead limit exceeded — "
                f"full GC running every 3 seconds\n"
                f"{ts()} jvm[java]: OldGen space full — "
                f"OutOfMemoryError imminent\n"
                f"{ts()} dynatrace-apm: Memory leak in {svc} v{random.randint(2,4)}."
                f"{random.randint(1,9)}.{random.randint(0,5)} — "
                f"object retention in cache layer"
            ),
            "severity": "High",
        },
        {
            "alert": f"IMS VoIP Call Drop Rate High — {random.choice(TELECOM_NODES)}",
            "log": (
                f"{ts()} {random.choice(TELECOM_NODES)} ims-cscf[88]: "
                f"Call drop rate: {random.randint(15,35)}% (threshold: 5%)\n"
                f"{ts()} {random.choice(TELECOM_NODES)} ims-cscf[88]: "
                f"SIP 503 Service Unavailable from P-CSCF\n"
                f"{ts()} {random.choice(TELECOM_NODES)} ims-cscf[88]: "
                f"Media gateway overloaded — RTP packet loss {random.randint(8,20)}%\n"
                f"{ts()} {random.choice(TELECOM_NODES)} ims-cscf[88]: "
                f"Subscribers affected: {random.randint(500,2000)}"
            ),
            "severity": "Critical",
        },
    ])


# ── Generator ────────────────────────────────────────────────────────────────

SOURCES = {
    "Network":     "SolarWinds NPM",
    "Security":    "FortiSIEM",
    "Hardware":    "HP iLO / IPMI",
    "Cloud":       "CloudWatch / Azure Monitor",
    "Application": "Dynatrace APM",
}

GENERATORS = {
    "Network":     network_alerts,
    "Security":    security_alerts,
    "Hardware":    hardware_alerts,
    "Cloud":       cloud_alerts,
    "Application": application_alerts,
}

# Realistic severity distribution for a telecom NOC
SEVERITY_WEIGHTS = {
    "Critical": 0.20,
    "High":     0.40,
    "Medium":   0.30,
    "Low":      0.10,
}

# Realistic category distribution
CATEGORY_WEIGHTS = {
    "Network":     0.30,
    "Security":    0.20,
    "Hardware":    0.15,
    "Cloud":       0.20,
    "Application": 0.15,
}


def generate_noc_tickets(num_tickets=50):
    tickets = []
    base_time = datetime.now() - timedelta(hours=8)
    categories = list(CATEGORY_WEIGHTS.keys())
    cat_probs = list(CATEGORY_WEIGHTS.values())

    for i in range(1, num_tickets + 1):
        category = random.choices(categories, weights=cat_probs, k=1)[0]
        issue = GENERATORS[category]()
        ticket_time = base_time + timedelta(minutes=random.randint(0, 480))

        tickets.append({
            "Ticket_ID":    f"INC-{3000 + i:04d}",
            "Timestamp":    ticket_time.strftime("%Y-%m-%d %H:%M"),
            "Source":       SOURCES[category],
            "Category":     category,
            "Severity":     issue["severity"],
            "Alert_Message": issue["alert"],
            "Raw_Logs":     issue["log"],
            "Status":       "Pending",
        })

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(tickets).sort_values("Timestamp").reset_index(drop=True)
    df.to_csv("data/mock_tickets.csv", index=False, encoding="utf-8")

    print(f"✅ Generated {num_tickets} tickets → data/mock_tickets.csv\n")
    print("Category breakdown:")
    print(df["Category"].value_counts().to_string())
    print("\nSeverity breakdown:")
    print(df["Severity"].value_counts().to_string())
    print(f"\nUnique alert types: {df['Alert_Message'].nunique()}")


if __name__ == "__main__":
    generate_noc_tickets(50)
