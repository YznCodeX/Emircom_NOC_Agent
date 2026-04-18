import os
import json
import sqlite3
import requests
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

def print_arabic(text):
    print(text)

# Raw Groq SDK shim — exposes .invoke(prompt) and .stream(messages) like the
# langchain_groq ChatGroq we used before. langchain_groq's import hangs on
# Python 3.14 due to pydantic v1 incompatibility, so we call Groq directly.
from dataclasses import dataclass

_MODEL = "llama-3.3-70b-versatile"
_TEMP = 0.1

@dataclass
class _Msg:
    content: str

class _LazyLLM:
    def __init__(self):
        self._client = None

    def _get(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq()
        return self._client

    @staticmethod
    def _to_messages(prompt_or_messages):
        if isinstance(prompt_or_messages, str):
            return [{"role": "user", "content": prompt_or_messages}]
        out = []
        for m in prompt_or_messages:
            if isinstance(m, dict):
                out.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            else:
                out.append({"role": getattr(m, "role", "user"), "content": getattr(m, "content", str(m))})
        return out

    def invoke(self, prompt):
        resp = self._get().chat.completions.create(
            model=_MODEL, temperature=_TEMP, messages=self._to_messages(prompt),
        )
        return _Msg(content=resp.choices[0].message.content or "")

    def stream(self, messages):
        s = self._get().chat.completions.create(
            model=_MODEL, temperature=_TEMP, messages=self._to_messages(messages), stream=True,
        )
        for chunk in s:
            delta = chunk.choices[0].delta.content
            if delta:
                yield _Msg(content=delta)

llm = _LazyLLM()

# ── Dedup persistence — SQLite-backed alert history ──────────────────────────
def _init_dedup_db(conn):
    """Create the dedup table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dedup_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id   TEXT NOT NULL,
            description TEXT NOT NULL,
            seen_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

def _dedup_add(conn, ticket_id: str, description: str):
    conn.execute(
        "INSERT INTO dedup_alerts (ticket_id, description) VALUES (?, ?)",
        (ticket_id, description)
    )
    conn.commit()

def _dedup_get_recent(conn, limit: int = 10) -> list:
    """Return the last N alerts as [{'id': ..., 'desc': ...}]."""
    rows = conn.execute(
        "SELECT ticket_id, description FROM dedup_alerts ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [{"id": r[0], "desc": r[1]} for r in reversed(rows)]

def _dedup_ticket_seen(conn, ticket_id: str) -> bool:
    """Return True if this exact ticket_id was already processed."""
    row = conn.execute(
        "SELECT 1 FROM dedup_alerts WHERE ticket_id = ? LIMIT 1",
        (ticket_id,)
    ).fetchone()
    return row is not None

# Cache for root cause correlation — stores analyzed tickets
correlation_cache = []

class AgentState(TypedDict):
    ticket_id: str
    category: str
    description: str
    logs: str
    analysis: str
    is_duplicate: bool
    duplicate_reason: str
    is_correlated: bool
    correlated_with: str
    confidence_score: int  # 0-100
    severity: str
    recommendation: str
    glpi_ticket_id: str
    supervisor_reason: str  # why supervisor picked this specialist
    runbook_match: str      # formatted runbook text from RAG, "" if no match

def triage_node(state: AgentState):
    print_arabic(f"\n[{state['ticket_id']}] 🔍 Triage Station: Receiving and routing alert...")
    return state

# --- 🧠 Deduplication Engine (SQLite-backed) ---
def deduplication_node(state: AgentState):
    print(f"[{state['ticket_id']}] 🪞 Deduplication Engine: Checking for alert storms...")

    # Exact ticket_id match — already processed this ticket
    if _dedup_ticket_seen(_conn, state['ticket_id']):
        return {"is_duplicate": True, "duplicate_reason": f"Ticket {state['ticket_id']} already processed in this or a previous session"}

    recent = _dedup_get_recent(_conn, limit=10)

    if not recent:
        _dedup_add(_conn, state['ticket_id'], state['description'])
        return {"is_duplicate": False, "duplicate_reason": "First alert in system"}

    recent_alerts_str = "\n".join([f"- ID: {a['id']} | Desc: {a['desc']}" for a in recent])

    prompt = f"""
    You are an AI assistant in Emircom's NOC.
    Determine if the NEW alert is a duplicate of any RECENT alerts (part of an alert storm).
    An alert is a duplicate ONLY if it involves the SAME issue on the SAME device/IP.

    RECENT ALERTS (last 10, persisted across restarts):
    {recent_alerts_str}

    NEW ALERT:
    ID: {state['ticket_id']}
    Description: {state['description']}

    Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "is_duplicate": (true or false),
      "reason": "(Short explanation why it is or isn't a duplicate)"
    }}
    """

    try:
        response = llm.invoke(prompt)
        raw_text = response.content.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"[{state['ticket_id']}] ⚠️ Dedup JSON parse error: {e}")
            _dedup_add(_conn, state['ticket_id'], state['description'])
            return {"is_duplicate": False, "duplicate_reason": f"DEDUP_WARN: invalid JSON — treated as unique"}

        is_dup = parsed.get("is_duplicate", False)
        reason = parsed.get("reason", "Unknown")

        if not is_dup:
            _dedup_add(_conn, state['ticket_id'], state['description'])

        return {"is_duplicate": is_dup, "duplicate_reason": reason}

    except Exception as e:
        print(f"[{state['ticket_id']}] ❌ Dedup error: {type(e).__name__}: {e}")
        _dedup_add(_conn, state['ticket_id'], state['description'])
        return {"is_duplicate": False, "duplicate_reason": f"DEDUP_ERROR: {type(e).__name__} — treated as unique"}

# --- 🗑️ محطة التذاكر المكررة (Drop Node) ---
def drop_node(state: AgentState):
    print(f"[{state['ticket_id']}] 🗑️ Alert Dropped: {state.get('duplicate_reason')}")
    # توليد JSON وهمي عشان الواجهة تعرضه لك
    mock_analysis = {
        "Categorization": "Duplicate / Alert Storm",
        "Affected_Node": "Multiple/Same as previous",
        "Severity": "Info",
        "Business_Impact": "None - Duplicate Alert suppressed.",
        "Symptom_Description": state['description'],
        "Root_Cause": "Alert Storm (Repeated System Event)",
        "Recommended_Action": f"DROP ALERT: {state.get('duplicate_reason')}"
    }
    return {"analysis": json.dumps(mock_analysis, indent=2)}

def network_ops_node(state: AgentState):
    prompt = f"""
    You are an expert Network Engineer at Emircom's NOC.
    Analyze the following issue based on the logs:
    Alert Description: {state['description']}
    Raw Logs: {state['logs']}

    Extract the critical incident data strictly following ITSM best practices. Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "Categorization": "(e.g., Routing, Switching, Hardware, Performance)",
      "Affected_Node": "(Extract the specific IP, Interface, or Device name)",
      "Severity": "(Choose one: Critical, High, Medium, Low)",
      "Business_Impact": "(Briefly assess the impact on operations based on the severity)",
      "Symptom_Description": "(Clear, professional description of the visible issue)",
      "Root_Cause": "(One precise sentence explaining the root cause based on logs)",
      "Recommended_Action": "(Specific technical action to resolve the issue)",
      "Confidence_Score": "(Integer 0-100: how confident you are in this analysis based on log quality and clarity. 90+ = clear logs with definitive root cause, 70-89 = good evidence but some ambiguity, 50-69 = partial logs or multiple possible causes, below 50 = insufficient data)",
      "Confidence_Reason": "(One sentence explaining what drove the confidence score up or down)"
    }}
    """
    response = llm.invoke(prompt)
    raw = response.content
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
        score = int(parsed.get("Confidence_Score", 75))
    except Exception:
        score = 75
    return {"analysis": raw, "confidence_score": score}

def security_ops_node(state: AgentState):
    prompt = f"""
    You are an expert Cyber Security Engineer at Emircom's SOC.
    Analyze the following security alert based on the logs:
    Alert Description: {state['description']}
    Raw Logs: {state['logs']}

    Extract the critical incident data strictly following ITSM best practices. Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "Categorization": "(e.g., Malware, Brute Force, DoS, Unauthorized Access)",
      "Affected_Node": "(Extract the targeted IP, Port, or User account)",
      "Severity": "(Choose one: Critical, High, Medium, Low)",
      "Business_Impact": "(Briefly assess the security risk and impact on the organization)",
      "Symptom_Description": "(Clear, professional description of the security threat)",
      "Root_Cause": "(One precise sentence explaining the vulnerability or attack vector)",
      "Recommended_Action": "(Specific technical action to mitigate the threat)",
      "Confidence_Score": "(Integer 0-100: how confident you are in this analysis based on log quality and clarity. 90+ = clear attack signature with definitive IOCs, 70-89 = good evidence but some ambiguity, 50-69 = partial logs or multiple possible attack vectors, below 50 = insufficient data)",
      "Confidence_Reason": "(One sentence explaining what drove the confidence score up or down)"
    }}
    """
    response = llm.invoke(prompt)
    raw = response.content
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
        score = int(parsed.get("Confidence_Score", 75))
    except Exception:
        score = 75
    return {"analysis": raw, "confidence_score": score}

def hardware_ops_node(state: AgentState):
    prompt = f"""
    You are an expert Hardware/Field Engineer at Emircom's NOC.
    Analyze the following hardware incident based on the logs:
    Alert Description: {state['description']}
    Raw Logs: {state['logs']}

    Extract the critical incident data strictly following ITSM best practices. Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "Categorization": "(e.g., Power Failure, Fan Failure, Disk Failure, Optical Transceiver, Physical Damage)",
      "Affected_Node": "(Extract the specific device, chassis, slot, or component name)",
      "Severity": "(Choose one: Critical, High, Medium, Low)",
      "Business_Impact": "(Briefly assess the operational impact of the hardware fault)",
      "Symptom_Description": "(Clear, professional description of the hardware fault observed)",
      "Root_Cause": "(One precise sentence identifying the faulty component and failure mode)",
      "Recommended_Action": "(Specific action: RMA, on-site dispatch, spare part replacement, etc.)",
      "Confidence_Score": "(Integer 0-100: confidence in diagnosis. 90+ = clear hardware fault with specific component identified, 70-89 = probable fault with some ambiguity, below 70 = requires on-site inspection)",
      "Confidence_Reason": "(One sentence explaining what drove the confidence score up or down)"
    }}
    """
    response = llm.invoke(prompt)
    raw = response.content
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
        score = int(parsed.get("Confidence_Score", 70))
    except Exception:
        score = 70
    return {"analysis": raw, "confidence_score": score}

def cloud_ops_node(state: AgentState):
    prompt = f"""
    You are an expert Cloud Infrastructure Engineer at Emircom's NOC.
    Analyze the following cloud/virtualization incident based on the logs:
    Alert Description: {state['description']}
    Raw Logs: {state['logs']}

    Extract the critical incident data strictly following ITSM best practices. Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "Categorization": "(e.g., VM Crash, Storage Latency, Hypervisor Fault, Network Overlay, API Failure, Auto-scaling)",
      "Affected_Node": "(Extract the VM name, cluster, availability zone, or cloud resource ID)",
      "Severity": "(Choose one: Critical, High, Medium, Low)",
      "Business_Impact": "(Briefly assess the impact on cloud-hosted services and workloads)",
      "Symptom_Description": "(Clear, professional description of the cloud infrastructure issue)",
      "Root_Cause": "(One precise sentence explaining the cloud-layer root cause)",
      "Recommended_Action": "(Specific action: failover, snapshot restore, scale-out, provider escalation, etc.)",
      "Confidence_Score": "(Integer 0-100: confidence in diagnosis based on telemetry quality. 90+ = clear failure with definitive logs, 70-89 = probable cause with some ambiguity, below 70 = requires deeper investigation)",
      "Confidence_Reason": "(One sentence explaining what drove the confidence score up or down)"
    }}
    """
    response = llm.invoke(prompt)
    raw = response.content
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
        score = int(parsed.get("Confidence_Score", 75))
    except Exception:
        score = 75
    return {"analysis": raw, "confidence_score": score}

def application_ops_node(state: AgentState):
    prompt = f"""
    You are an expert Application Support Engineer at Emircom's NOC.
    Analyze the following application/service incident based on the logs:
    Alert Description: {state['description']}
    Raw Logs: {state['logs']}

    Extract the critical incident data strictly following ITSM best practices. Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "Categorization": "(e.g., Service Crash, High Latency, Database Error, API Timeout, Memory Leak, Config Error)",
      "Affected_Node": "(Extract the service name, server, database, or application endpoint)",
      "Severity": "(Choose one: Critical, High, Medium, Low)",
      "Business_Impact": "(Briefly assess the impact on end-users and business operations)",
      "Symptom_Description": "(Clear, professional description of the application failure)",
      "Root_Cause": "(One precise sentence explaining the application-layer root cause)",
      "Recommended_Action": "(Specific action: restart service, rollback deployment, patch, escalate to dev team, etc.)",
      "Confidence_Score": "(Integer 0-100: confidence in diagnosis. 90+ = clear error with stack trace or definitive logs, 70-89 = probable cause, below 70 = ambiguous logs requiring deeper investigation)",
      "Confidence_Reason": "(One sentence explaining what drove the confidence score up or down)"
    }}
    """
    response = llm.invoke(prompt)
    raw = response.content
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
        score = int(parsed.get("Confidence_Score", 75))
    except Exception:
        score = 75
    return {"analysis": raw, "confidence_score": score}

def correlation_node(state: AgentState):
    print(f"[{state['ticket_id']}] 🔗 Correlation Engine: Checking for related incidents...")

    try:
        raw_analysis = state.get("analysis", "")
        parsed = json.loads(raw_analysis.replace("```json", "").replace("```", "").strip())
        affected_node = parsed.get("Affected_Node", "")
        root_cause = parsed.get("Root_Cause", "")
        categorization = parsed.get("Categorization", "")
    except Exception:
        affected_node = ""
        root_cause = state.get("description", "")
        categorization = state.get("category", "")

    if not correlation_cache:
        correlation_cache.append({
            "id": state["ticket_id"],
            "affected_node": affected_node,
            "root_cause": root_cause,
            "categorization": categorization
        })
        return {"is_correlated": False, "correlated_with": ""}

    recent_str = "\n".join([
        f"- ID: {t['id']} | Node: {t['affected_node']} | Category: {t['categorization']} | Root Cause: {t['root_cause']}"
        for t in correlation_cache[-10:]
    ])

    prompt = f"""
    You are a senior NOC engineer at Emircom.
    Determine if the CURRENT incident shares the same ROOT CAUSE as any RECENT incidents.
    Two incidents are correlated if they affect the same device/network segment OR if one could cause the other.

    RECENT INCIDENTS:
    {recent_str}

    CURRENT INCIDENT:
    ID: {state['ticket_id']}
    Affected Node: {affected_node}
    Category: {categorization}
    Root Cause: {root_cause}

    Respond ONLY with a valid JSON object. Do not include markdown formatting. Use exactly this structure:
    {{
      "is_correlated": (true or false),
      "correlated_with": "(Comma-separated list of correlated ticket IDs, or empty string if none)",
      "reason": "(One sentence explaining the correlation or why there is none)"
    }}
    """

    try:
        response = llm.invoke(prompt)
        raw_text = response.content.replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"[{state['ticket_id']}] ⚠️ Correlation JSON parse error: {e}")
            correlation_cache.append({"id": state["ticket_id"], "affected_node": affected_node, "root_cause": root_cause, "categorization": categorization})
            return {"is_correlated": False, "correlated_with": ""}

        is_corr = result.get("is_correlated", False)
        corr_with = result.get("correlated_with", "")
        reason = result.get("reason", "")

        correlation_cache.append({"id": state["ticket_id"], "affected_node": affected_node, "root_cause": root_cause, "categorization": categorization})

        if is_corr:
            print(f"[{state['ticket_id']}] 🔗 Correlated with: {corr_with} — {reason}")

        return {"is_correlated": is_corr, "correlated_with": corr_with}

    except Exception as e:
        print(f"[{state['ticket_id']}] ❌ Correlation API error: {type(e).__name__}: {e}")
        correlation_cache.append({"id": state["ticket_id"], "affected_node": affected_node, "root_cause": root_cause, "categorization": categorization})
        return {"is_correlated": False, "correlated_with": ""}


GLPI_URL = "http://localhost/api.php/v1"
GLPI_USER = "glpi"
GLPI_PASS = "glpi"
GLPI_APP_TOKEN = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"

PRIORITY_MAP = {"Critical": 6, "High": 4, "Medium": 3, "Low": 2}

CATEGORY_IDS = {"Network": 1, "Security": 2, "Hardware": 3, "Cloud": 4, "Application": 5}

# Group IDs — must match what glpi_agent.py creates at startup
# These are fetched once at first use and cached
_GROUP_ID_CACHE: dict = {}

def _get_group_id(headers: dict, category: str) -> int | None:
    """Fetch GLPI group ID for a category, with in-process caching."""
    global _GROUP_ID_CACHE
    if category in _GROUP_ID_CACHE:
        return _GROUP_ID_CACHE[category]

    team_names = {
        "Network":     "NOC Network Team",
        "Security":    "NOC Security Team",
        "Hardware":    "NOC Hardware Team",
        "Cloud":       "NOC Cloud Team",
        "Application": "NOC Application Team",
    }
    target_name = team_names.get(category)
    if not target_name:
        return None

    try:
        r = requests.get(
            f"{GLPI_URL}/Group",
            headers=headers,
            params={"range": "0-50", "searchText[name]": target_name},
            timeout=5,
        )
        groups = r.json() if isinstance(r.json(), list) else []
        for g in groups:
            if g.get("name") == target_name:
                _GROUP_ID_CACHE[category] = g["id"]
                return g["id"]
    except Exception:
        pass
    return None


def _glpi_create_ticket(title: str, description: str, priority: str, category: str = "") -> str:
    """Create a ticket in GLPI with group assigned at creation time."""
    try:
        # Step 1: Get session token
        auth = requests.get(
            f"{GLPI_URL}/initSession",
            headers={
                "Content-Type": "application/json",
                "App-Token": GLPI_APP_TOKEN,
                "Authorization": "user_token GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"
            },
            timeout=5
        )
        if auth.status_code != 200:
            return f"GLPI auth failed: {auth.status_code}"
        session_token = auth.json().get("session_token")

        headers = {
            "Content-Type": "application/json",
            "Session-Token": session_token,
            "App-Token": GLPI_APP_TOKEN,
        }

        # Step 2: Create ticket
        ticket_input = {
            "name": title,
            "content": description,
            "priority": PRIORITY_MAP.get(priority, 3),
            "urgency": PRIORITY_MAP.get(priority, 3),
            "impact": PRIORITY_MAP.get(priority, 3),
            "type": 1,   # Incident
            "status": 2, # Processing (assigned)
        }
        cat_id = CATEGORY_IDS.get(category)
        if cat_id:
            ticket_input["itilcategories_id"] = cat_id

        resp = requests.post(f"{GLPI_URL}/Ticket", headers=headers,
                             json={"input": ticket_input}, timeout=5)
        ticket_id = resp.json().get("id", "unknown")

        # Step 3: Assign group immediately — so email includes the group
        if ticket_id and ticket_id != "unknown":
            group_id = _get_group_id(headers, category)
            if group_id:
                requests.post(
                    f"{GLPI_URL}/Group_Ticket",
                    headers=headers,
                    json={"input": {
                        "tickets_id": ticket_id,
                        "groups_id":  group_id,
                        "type":       2,  # 2 = assigned group
                    }},
                    timeout=5,
                )

        # Step 4: Kill session
        requests.get(f"{GLPI_URL}/killSession", headers=headers, timeout=5)

        return str(ticket_id)
    except Exception as e:
        return f"GLPI error: {e}"

def remedy_node(state: AgentState):
    analysis_raw = state.get("analysis", "{}")
    severity           = "Medium"
    categorization     = state.get("category", "Unknown")
    affected_node      = state.get("ticket_id", "")
    symptom            = ""
    root_cause         = ""
    business_impact    = ""
    recommended_action = ""
    confidence         = ""

    try:
        analysis       = json.loads(analysis_raw.replace("```json", "").replace("```", "").strip())
        severity           = analysis.get("Severity", "Medium")
        affected_node      = analysis.get("Affected_Node", "")
        categorization     = analysis.get("Categorization", state.get("category", "Unknown"))
        symptom            = analysis.get("Symptom_Description", "")
        root_cause         = analysis.get("Root_Cause", "")
        business_impact    = analysis.get("Business_Impact", "")
        recommended_action = analysis.get("Recommended_Action", "")
        confidence         = analysis.get("Confidence_Score", "")

        description = (
            f"🤖 AI NOC Agent Analysis\n"
            f"{'='*50}\n\n"
            f"Ticket ID:        {state.get('ticket_id', '')}\n"
            f"Severity:         {severity}\n"
            f"Affected Node:    {affected_node}\n"
            f"Categorization:   {categorization}\n"
            f"Confidence Score: {confidence}%\n\n"
            f"SYMPTOM\n{'-'*30}\n{symptom}\n\n"
            f"ROOT CAUSE\n{'-'*30}\n{root_cause}\n\n"
            f"BUSINESS IMPACT\n{'-'*30}\n{business_impact}\n\n"
            f"RECOMMENDED ACTION\n{'-'*30}\n{recommended_action}\n"
        )
    except Exception:
        description = analysis_raw

    title = f"[NOC] {categorization} — {affected_node}"

    glpi_id = _glpi_create_ticket(title, description, severity, categorization)
    print(f"[{state['ticket_id']}] GLPI Ticket Created: #{glpi_id}")

    # Send email directly via Gmail SMTP (bypasses GLPI's cron)
    try:
        from src.email_sender import send_alert_email
        send_alert_email(
            ticket_id          = state.get("ticket_id", ""),
            glpi_ticket_id     = str(glpi_id),
            category           = categorization,
            severity           = severity,
            affected_node      = affected_node,
            symptom            = symptom,
            root_cause         = root_cause,
            recommended_action = recommended_action,
            business_impact    = business_impact,
            confidence_score   = str(confidence),
            correlated_with    = state.get("correlated_with", ""),
        )
    except Exception as e:
        print(f"[{state['ticket_id']}] ⚠️ Email error: {e}")

    return {"glpi_ticket_id": glpi_id}

# --- 📖 Runbook Agent Node — RAG-based procedure retrieval ---
def runbook_node(state: AgentState):
    """Search the Emircom runbook library for a matching procedure.
    Called AFTER the specialist node so category is LLM-confirmed.
    Stores the formatted runbook in state['runbook_match'].
    On error or no match, stores "" — HITL panel hides the section gracefully."""
    print(f"[{state['ticket_id']}] 📖 Runbook Agent: Searching runbook library...")
    try:
        from src.rag_core import find_matching_runbook
        match = find_matching_runbook(
            description=state.get("description", ""),
            logs=state.get("logs", ""),
            category=state.get("category", ""),
            llm=llm,
        )
        if match:
            print(f"[{state['ticket_id']}] 📖 Runbook matched — {len(match)} chars")
        else:
            print(f"[{state['ticket_id']}] 📖 No runbook match above threshold")
        return {"runbook_match": match}
    except Exception as e:
        print(f"[{state['ticket_id']}] ⚠️ Runbook node error: {type(e).__name__}: {e}")
        return {"runbook_match": ""}


# --- Supervisor Node — LLM-based alert classification ---
def supervisor_node(state: AgentState):
    """Read raw alert and decide which specialist team should handle it.
    Overwrites caller-provided category with LLM judgment."""
    prompt = f"""You are the NOC Supervisor at Emircom. Classify this alert and route it to the right specialist team.

Alert Description: {state['description']}
Raw Logs: {state['logs']}

Specialist teams:
- Network: routing protocols (BGP/OSPF), interfaces, links, VPN, MPLS, bandwidth, wireless, cell towers
- Security: firewall denies, intrusion detection, malware, brute force, unauthorized access, certificates
- Hardware: PSU failure, fans, disk failure, temperature, UPS, optical transceivers, physical device faults
- Cloud: VMs, containers, Kubernetes, hypervisors, cloud storage, auto-scaling, cloud API failures
- Application: web services, databases, API timeouts, memory leaks, service crashes, deployment issues

Respond ONLY with valid JSON, no markdown:
{{"category": "Network", "confidence": 92, "reason": "OSPF adjacency loss on CE-MPLS-01 indicates a routing protocol issue"}}"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        category = parsed.get("category", "").strip()
        reason = parsed.get("reason", "")
        if category not in ("Network", "Security", "Hardware", "Cloud", "Application"):
            raise ValueError(f"Unknown category: {category!r}")
        print(f"[{state['ticket_id']}] 🎯 Supervisor → {category} ({parsed.get('confidence', '?')}% confidence): {reason}")
        return {"category": category, "supervisor_reason": reason}
    except Exception as e:
        print(f"[{state['ticket_id']}] ⚠️ Supervisor fallback to caller category '{state['category']}': {e}")
        return {"supervisor_reason": f"Supervisor error — kept caller category: {e}"}

# --- بناء الجراف مع المسارات الجديدة ---
_conn = sqlite3.connect("data/noc_memory.db", check_same_thread=False)
_init_dedup_db(_conn)  # ensure dedup table exists
memory = SqliteSaver(_conn)
workflow = StateGraph(AgentState)

workflow.add_node("triage", triage_node)
workflow.add_node("deduplication", deduplication_node)
workflow.add_node("drop", drop_node)
workflow.add_node("network_ops", network_ops_node)
workflow.add_node("security_ops", security_ops_node)
workflow.add_node("hardware_ops", hardware_ops_node)
workflow.add_node("cloud_ops", cloud_ops_node)
workflow.add_node("application_ops", application_ops_node)
workflow.add_node("runbook", runbook_node)
workflow.add_node("correlation", correlation_node)
workflow.add_node("remedy", remedy_node)

workflow.set_entry_point("triage")
workflow.add_edge("triage", "deduplication")

CATEGORY_ROUTING = {
    "Network":     "network_ops",
    "Security":    "security_ops",
    "Hardware":    "hardware_ops",
    "Cloud":       "cloud_ops",
    "Application": "application_ops",
}

def route_after_dedup(state: AgentState):
    if state.get("is_duplicate"):
        return "drop"
    return "supervisor"

def route_after_supervisor(state: AgentState):
    return CATEGORY_ROUTING.get(state["category"], "network_ops")

workflow.add_node("supervisor", supervisor_node)

workflow.add_conditional_edges(
    "deduplication",
    route_after_dedup,
    {"drop": "drop", "supervisor": "supervisor"}
)

workflow.add_conditional_edges(
    "supervisor",
    route_after_supervisor,
    {"network_ops": "network_ops", "security_ops": "security_ops",
     "hardware_ops": "hardware_ops", "cloud_ops": "cloud_ops", "application_ops": "application_ops"}
)

workflow.add_edge("drop", END)
# Specialist → Runbook (RAG) → Correlation
workflow.add_edge("network_ops",     "runbook")
workflow.add_edge("security_ops",    "runbook")
workflow.add_edge("hardware_ops",    "runbook")
workflow.add_edge("cloud_ops",       "runbook")
workflow.add_edge("application_ops", "runbook")
workflow.add_edge("runbook", "correlation")
workflow.add_edge("correlation", "remedy")
workflow.add_edge("remedy", END)

app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["remedy", "drop"] # الأيجنت بيوقف ويستأذنك قبل فتح التذكرة وقبل الحذف!
)