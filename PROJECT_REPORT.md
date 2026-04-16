# Emircom NOC Agent — Technical Documentation

**Version:** 1.3  
**Date:** April 16, 2026  
**Author:** Yazan  
**Status:** Prototype — pending supervisor approval for production data access

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Project Structure](#3-project-structure)
4. [Core Agent (`src/agent_graph.py`)](#4-core-agent)
5. [Streamlit Interface (`streamlit/app.py`)](#5-streamlit-interface)
6. [GLPI Integration (`glpi/`)](#6-glpi-integration)
7. [React Interface (`frontend/` + `react/`)](#7-react-interface)
8. [Data Layer (`data/`)](#8-data-layer)
9. [Configuration & Environment](#9-configuration--environment)
10. [Startup & Deployment](#10-startup--deployment)
11. [API Reference](#11-api-reference)
12. [Feature Status](#12-feature-status)
13. [Known Limitations](#13-known-limitations)
14. [Future Roadmap](#14-future-roadmap)

---

## 1. Project Overview

### Purpose
The Emircom NOC Agent is an AI-powered system designed to automate the manual work performed by Network Operations Center (NOC) engineers at Emircom. The NOC operates 24/7 and engineers spend significant time on repetitive triage tasks — reading alerts, classifying severity, assigning tickets to teams, writing notifications, and generating shift reports.

This system uses a Large Language Model (LLaMA 3.3 70B via Groq) orchestrated by LangGraph to perform that triage automatically, while keeping engineers in the loop for final decisions (Human-in-the-Loop architecture).

### What the NOC Does Today (Manual Process)
- Receives alerts from monitoring systems
- Classifies severity (Critical / High / Medium / Low)
- Identifies the responsible team
- Creates a ticket in Remedy (ITSM system)
- Sends email notifications to teams using a standard table-format template
- Tracks SLA compliance
- Writes shift handoff reports

### What the Agent Automates
- Severity classification
- Root cause analysis
- Duplicate detection (same alert, multiple triggers)
- Cross-ticket root cause correlation
- Team routing
- Email template generation
- GLPI ticket creation and assignment
- Shift handoff report generation

### Design Principle: Human-in-the-Loop (HITL)
The agent never takes final action autonomously. Every analyzed ticket is presented to an engineer who reviews the AI output and clicks **Approve** or **Reject**. This is intentional — the agent assists but the engineer decides.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Data Sources                        │
│   CSV Alerts / Mock Tickets / Future: Real ITSM Feed    │
└──────────────────────────┬──────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
   ┌──────────────┐ ┌────────────┐ ┌─────────────────┐
   │   Streamlit  │ │   React    │ │      GLPI        │
   │  Port 8501   │ │ Port 5173  │ │   Port 80        │
   │  (Original)  │ │  (New UI)  │ │  (ITSM System)   │
   └──────┬───────┘ └─────┬──────┘ └────────┬─────────┘
          │               │                  │
          │          ┌────▼─────┐    ┌───────▼──────────┐
          │          │ FastAPI  │    │  glpi_agent.py   │
          │          │Port 8001 │    │  (polls 15s)     │
          │          └────┬─────┘    └───────┬──────────┘
          │               │                  │
          └───────────────┼──────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │     src/agent_graph.py        │
          │   LangGraph AI Agent          │
          │                               │
          │  Triage → Dedup → Analysis    │
          │  → Correlation → HITL         │
          └───────────────┬───────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │   Groq API — LLaMA 3.3 70B   │
          └───────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │   data/noc_memory.db          │
          │   SqliteSaver (LangGraph)     │
          └───────────────────────────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| `src/agent_graph.py` | The AI brain — shared by all interfaces |
| `streamlit/app.py` | Original full-featured NOC dashboard |
| `react/backend/main.py` | REST API connecting React to the agent and GLPI |
| `frontend/src/App.jsx` | React dashboard — modern UI |
| `glpi/glpi_agent.py` | Background worker — polls GLPI and runs AI analysis |
| `glpi/push_to_glpi.py` | Test utility — pushes mock tickets into GLPI |
| `start_noc.ps1` | One-command startup — starts all services |

---

## 3. Project Structure

```
Emircom_NOC_Agent/
│
├── src/
│   ├── agent_graph.py          # Core AI agent (LangGraph state machine)
│   └── rag_core.py             # RAG module (BGE-M3 embeddings — ready, not wired)
│
├── streamlit/
│   └── app.py                  # Full-featured Streamlit NOC dashboard
│
├── glpi/
│   ├── glpi_agent.py           # Background polling worker for GLPI
│   └── push_to_glpi.py         # Test script — pushes CSV tickets to GLPI
│
├── react/
│   └── backend/
│       └── main.py             # FastAPI backend (port 8001)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # React dashboard (main component)
│   │   ├── App.css             # Styles
│   │   ├── main.jsx            # React entry point
│   │   └── index.css           # Global styles
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   ├── mock_tickets.csv        # 40+ mock NOC incident tickets
│   ├── processed_tickets.json  # Audit log of all approved/rejected tickets
│   ├── noc_memory.db           # SqliteSaver — LangGraph agent memory
│   ├── session_state.json      # Persists ticket index across restarts
│   └── emircom_runbooks/       # Empty — waiting for real runbook data
│
├── .env                        # API keys (GROQ_API_KEY, GLPI tokens)
├── requirements.txt            # Python dependencies
├── start_noc.ps1               # One-command startup script
└── START_GLPI.md               # Quick-start guide
```

---

## 4. Core Agent

**File:** `src/agent_graph.py`

### Overview
The agent is a LangGraph state machine with multiple nodes. All three interfaces (Streamlit, React, GLPI) invoke this same agent — it is the shared brain of the system.

### Agent State (`AgentState`)

```python
class AgentState(TypedDict):
    ticket_id: str
    category: str           # Network / Security / Hardware / Cloud / Application
    description: str
    logs: str
    analysis: str           # JSON string — full AI analysis output
    is_duplicate: bool
    duplicate_reason: str
    is_correlated: bool
    correlated_with: str    # Ticket ID of correlated ticket
    confidence_score: int   # 0-100
```

### Agent Graph Flow

```
START
  │
  ▼
triage_node          ← Classifies category and initial severity
  │
  ▼
dedup_node           ← Checks if this ticket is a duplicate of a recent one
  │
  ├── (duplicate) → drop_node → HITL interrupt (approve drop or keep)
  │
  └── (unique) → route by category
                    │
                    ├── network_ops_node
                    ├── security_ops_node
                    ├── hardware_ops_node
                    ├── cloud_ops_node
                    └── application_ops_node
                              │
                              ▼
                    correlation_node     ← Checks if root cause matches recent tickets
                              │
                              ▼
                    remedy_node          ← HITL interrupt (approve → create ticket)
                              │
                              ▼
                            END
```

### LLM Analysis Output (JSON)

Each analysis node produces a JSON object with these fields:

```json
{
  "Severity": "Critical | High | Medium | Low",
  "Affected_Node": "hostname or IP",
  "Categorization": "specific sub-category",
  "Symptom_Description": "what is happening",
  "Root_Cause": "why it is happening",
  "Business_Impact": "effect on operations",
  "Recommended_Action": "step-by-step remediation",
  "Confidence_Score": 85,
  "Confidence_Reason": "explanation of confidence level"
}
```

### Analysis Nodes (5 Specialists)

| Node | Category | Prompt Focus |
|------|----------|-------------|
| `network_ops_node` | Network | BGP, OSPF, VLAN, DHCP, DNS, bandwidth, interface flaps |
| `security_ops_node` | Security | Malware, DDoS, brute force, firewall, certificates |
| `hardware_ops_node` | Hardware | PSU, fans, disk, NIC, temperature, ECC memory |
| `cloud_ops_node` | Cloud | AWS, Azure, Kubernetes, EC2, S3, pod failures |
| `application_ops_node` | Application | ERP, SAP, API, database, SMTP, memory leaks |

### Persistence
- Agent state is stored in `data/noc_memory.db` using `SqliteSaver`
- Thread ID = Ticket ID (e.g., `GLPI-65` or `INC-1001`)
- State is retrieved by thread ID across restarts
- Correlation engine uses last 10 analyzed tickets from memory

### Configuration

```python
# LLM
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

# Memory
memory = SqliteSaver.from_conn_string("data/noc_memory.db")

# Graph interrupt points (HITL)
app = graph.compile(
    checkpointer=memory,
    interrupt_before=["remedy", "drop"]
)
```

---

## 5. Streamlit Interface

**File:** `streamlit/app.py`  
**Port:** 8501  
**Lines:** ~1288

### Tabs

#### Tab 1: Live Operations
- **Stats strip** — queue size, processed count, approved, rejected, duplicates, SLA breaches
- **Upcoming queue** — next 3 tickets preview
- **HITL Panel** — full ticket review interface:
  - Pipeline visualization (Triage → Dedup → Analysis → Correlation → HITL)
  - Left column: Summary tab, Raw Logs tab, Email Template tab
  - Right column: SLA Timer, Confidence Score, team routing info, Approve/Reject buttons
  - Dedup warning banner (orange)
  - Correlation warning banner (orange)
  - On-call escalation badge for Critical/High

#### Tab 2: Queue View
- Batch AI triage of all pending tickets
- Severity filter sidebar (All / Critical / High / Medium / Low with live counts)
- Per-ticket approve/reject inline — no modal required
- Correlation grouping visualization

#### Tab 3: Analytics Dashboard
- Performance metrics (total, approved, rejected, SLA breached)
- Bar charts: tickets by status, tickets by category
- Full audit log dataframe
- **Shift Handoff Report** section:
  - Outgoing/incoming engineer fields, shift period
  - LLM-generated report (shift narrative, critical incidents, watch list)
  - **Excel export** (3 sheets: Audit Log, Summary, By Category)
  - **Word export** (.docx with cover block, metrics table, AI incident summaries, watch list)

### SLA Thresholds

| Severity | SLA Window |
|----------|-----------|
| Critical | 15 minutes |
| High | 1 hour |
| Medium | 4 hours |
| Low | 24 hours |

### Team Routing

| Category | Team | Email |
|----------|------|-------|
| Network | Network Operations Team | `network-ops@emircom.com` |
| Security | Security Operations SOC | `soc-team@emircom.com` |
| Hardware | Field Engineering Team | `field-eng@emircom.com` |
| Cloud | Cloud Infrastructure Team | `cloud-ops@emircom.com` |
| Application | Application Support Team | `app-support@emircom.com` |

---

## 6. GLPI Integration

### What is GLPI?
GLPI is an open-source IT Service Management (ITSM) system, used here as a substitute for Remedy (which requires company IT approval). It runs via Docker and provides a full ticketing interface with REST API.

**GLPI URL:** `http://localhost`  
**Login:** `glpi / glpi`  
**API Base:** `http://localhost/api.php/v1`

### Docker Setup

```bash
docker start mariadb
docker start glpi
```

### Configured Elements

#### NOC Team Groups (auto-created by agent on startup)
| Group Name | Category |
|-----------|---------|
| NOC Network Team | Network |
| NOC Security Team | Security |
| NOC Hardware Team | Hardware |
| NOC Cloud Team | Cloud |
| NOC Application Team | Application |

#### SLA Rules
| SLA Name | TTR (Time to Resolve) | Calendar |
|----------|----------------------|---------|
| SLA - Critical | 15 minutes | 24/7 |
| SLA - High | 1 hour | 24/7 |
| SLA - Medium | 4 hours | 24/7 |
| SLA - Low | 24 hours | 24/7 |

#### GLPI Priority Mapping
| Severity | GLPI Priority Value |
|----------|-------------------|
| Critical | 6 |
| High | 4 |
| Medium | 3 |
| Low | 2 |

#### GLPI Ticket Status Mapping
| Status | Value | Meaning |
|--------|-------|---------|
| New | 1 | Freshly created |
| Processing | 2 | Being worked on |
| Pending | 4 | Awaiting engineer review (set by agent) |
| Solved | 5 | Engineer approved |
| Closed | 6 | Engineer rejected / closed |

#### ITIL Categories
| ID | Name |
|----|------|
| 1 | Network |
| 2 | Security |
| 3 | Hardware |
| 4 | Cloud |
| 5 | Application |

Auto-assigned when tickets are created via `_glpi_create_ticket()` using `CATEGORY_IDS` map in `agent_graph.py`.

#### Email Notifications
- **SMTP:** smtp.gmail.com, port 587
- **Account:** emircom.noc.agent@gmail.com (App Password configured)
- **Cron:** QueuedNotification runs every 1 minute automatically
- **Recipients:** Administrator + Group in charge of ticket
- **Template:** Custom branded "Emircom NOC Alert" HTML layout with ticket table, AI analysis, and View Ticket button
- **User:** `noc.agent` added to all 5 NOC groups to receive notifications

#### Dashboard Widgets (7 total)
| Widget | Type | Color |
|--------|------|-------|
| Total Tickets | Count | Red `#e74c3c` |
| Late Tickets | Count | Orange `#e67e22` |
| Solved Tickets | Count | Green `#27ae60` |
| Pending Tickets | Count | Blue `#3498db` |
| Tickets Status by Month | Bar chart | Navy `#2c3e50` |
| SLA Status by Technician Group | Horizontal stacked bars | Dark navy `#1a252f` |
| Top Assignee Groups | Donut chart | Navy `#2c3e50` |

---

### `glpi/glpi_agent.py` — Background Worker

**Purpose:** Polls GLPI every 15 seconds for unprocessed tickets and runs the AI agent on them.

**Startup sequence:**
1. Opens GLPI session
2. Calls `get_or_create_groups()` — ensures all 5 NOC team groups exist
3. Calls `load_sla_ids()` — fetches SLA IDs for later assignment
4. Closes session
5. Enters polling loop

**Per-ticket processing:**
1. Fetch tickets with status New (1) or Processing (2)
2. Skip tickets already in `processed_ids` set
3. Call `has_real_ai_comment()` — skip if already analyzed
4. Extract category from content (`Category: X` tag or keyword scan on title)
5. Run ticket through `agent_graph.py`
6. Post AI analysis as GLPI followup comment
7. Update ticket priority and set status to Pending (4)
8. Assign SLA based on severity
9. Assign NOC team group
10. Add ticket ID to `processed_ids`

**Duplicate prevention:** `has_real_ai_comment()` checks for `"AI NOC Agent Analysis"` string in existing comments. If found, ticket is skipped permanently.

**Error handling:** On Groq rate limit (429) or connection error, posts a user-friendly message instead of raw Python error:
> *"⚠️ AI analysis temporarily unavailable. The agent will retry this ticket automatically on the next cycle."*

---

### `glpi/push_to_glpi.py` — Test Utility

Reads `data/mock_tickets.csv` and creates GLPI tickets for each row. Used to populate GLPI with test data for demonstrations.

---

## 7. React Interface

### Frontend — `frontend/src/App.jsx`
**Port:** 5173 (Vite)  
**Tech:** React 18, Vite, Axios

#### Components

| Component | Purpose |
|-----------|---------|
| `SeverityBadge` | Colored pill badge (Critical/High/Medium/Low) |
| `StatCard` | Metric card (pending, approved, rejected, total) |
| `SLATimer` | Live countdown timer — green/yellow/red based on elapsed time |
| `TicketRow` | Single row in alert queue table |
| `TicketDetail` | Full-screen modal — AI analysis, SLA timer, tabs, actions |
| `HandoffReport` | Shift handoff report modal with Excel download |
| `GLPINotificationPanel` | Shows GLPI agent-analyzed tickets for review |
| `App` | Root component — state management and layout |

#### TicketDetail Tabs
1. **Summary** — AI analysis grid, symptom, recommended action, confidence bar
2. **Email Template** — pre-formatted team notification email, copy-to-clipboard

#### SLA Timer Logic
```
limitSecs = SLA_MINUTES[severity] * 60
elapsed = (Date.now() - openedAt) / 1000
remaining = max(0, limitSecs - elapsed)
pct = min(100, elapsed / limitSecs * 100)

color:
  pct < 50  → green  (#22c55e)
  pct < 80  → yellow (#f59e0b)
  pct >= 80 → red    (#ef4444)
```

#### GLPI Polling
React polls `/glpi/pending-review` every 15 seconds. New tickets (not previously seen) trigger:
- GLPI notification panel popup
- Browser push notification

---

### Backend — `react/backend/main.py`
**Port:** 8001 (Uvicorn)  
**Tech:** FastAPI, Pandas, openpyxl

See [API Reference](#11-api-reference) for full endpoint documentation.

---

## 8. Data Layer

### `data/mock_tickets.csv`
40+ realistic NOC incidents across all 5 categories.

**Columns:** `Ticket_ID, Category, Alert_Message, Raw_Logs, Severity, Timestamp`

**Categories covered:**
- **Network:** BGP failures, OSPF adjacency drops, DHCP pool exhaustion, interface flaps, bandwidth saturation, LACP failures, STP topology changes, WAN link outages
- **Security:** Malware detection, DDoS attacks, brute force attempts, SSL certificate expiry, ransomware indicators, unauthorized access, firewall ACL changes
- **Hardware:** PSU failures, fan failures, disk failures, NIC errors, temperature alerts, ECC memory errors
- **Cloud:** EC2 instance failures, S3 bucket issues, Kubernetes pod crashes, CDN outages, auto-scaling failures, VPC connectivity issues
- **Application:** ERP/SAP outages, API gateway errors, database replication lag, SMTP relay failures, memory leaks, billing system errors

### `data/processed_tickets.json`
Audit log. Each entry:
```json
{
  "Ticket_ID": "INC-1001",
  "Category": "Network",
  "Severity": "High",
  "Status": "Approved",
  "GLPI_Ticket": 42,
  "SLA_Breached": false,
  "Confidence_Score": "87"
}
```

### `data/noc_memory.db`
SQLite database used by LangGraph SqliteSaver. Stores full agent state per thread (ticket). Enables deduplication and correlation across sessions.

### `data/emircom_runbooks/`
Empty directory. Intended for real Emircom runbook documents (PDF/Word). When populated, `src/rag_core.py` will index them using BGE-M3 embeddings so the agent can reference SOPs during analysis.

---

## 9. Configuration & Environment

### `.env` File
```env
GROQ_API_KEY=your_groq_api_key_here
```

### GLPI Tokens (in `glpi/glpi_agent.py` and `react/backend/main.py`)
```python
GLPI_BASE  = "http://localhost/api.php/v1"
APP_TOKEN  = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN = "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"
```

### GLPI Agent Settings
```python
POLL_INTERVAL = 15   # seconds between ticket checks
```

---

## 10. Startup & Deployment

### One-Command Start (Recommended)
```powershell
.\start_noc.ps1
```

**What it does (in order):**
1. Checks if Docker Desktop is running — starts it if not (waits up to 60s)
2. Starts mariadb and glpi Docker containers
3. Opens FastAPI backend in new PowerShell window (port 8001)
4. Opens GLPI Agent worker in new PowerShell window (polls every 15s)
5. Opens React frontend in new PowerShell window (port 5173)

### Service URLs

| Service | URL | Credentials |
|---------|-----|------------|
| React Dashboard | http://localhost:5173 | — |
| Streamlit Dashboard | http://localhost:8501 | — |
| GLPI | http://localhost | glpi / glpi |
| FastAPI (Swagger Docs) | http://localhost:8001/docs | — |

### Manual Start (if needed)
```powershell
# 1. Docker
docker start mariadb
docker start glpi

# 2. Activate venv (in all terminals)
.\venv\Scripts\Activate.ps1

# 3. FastAPI backend
python -m uvicorn react.backend.main:app --port 8001

# 4. GLPI Agent worker
python glpi\glpi_agent.py

# 5. React frontend
cd frontend
npm run dev

# 6. Streamlit (optional)
streamlit run streamlit\app.py
```

### Push Mock Tickets to GLPI
```powershell
.\venv\Scripts\python.exe glpi\push_to_glpi.py
```

---

## 11. API Reference

**Base URL:** `http://localhost:8001`

### Tickets

#### `GET /tickets`
Returns all unprocessed tickets from CSV (excludes already processed IDs).

**Response:** Array of ticket objects from `mock_tickets.csv`

---

#### `GET /tickets/processed`
Returns full audit log of all approved/rejected tickets.

**Response:** Array of processed ticket records.

---

#### `POST /tickets/analyze`
Runs the AI agent on a ticket and returns the full analysis.

**Request body:**
```json
{
  "ticket_id": "INC-1001",
  "category": "Network",
  "description": "Core router BGP session down",
  "logs": "raw log content here"
}
```

**Response:**
```json
{
  "ticket_id": "INC-1001",
  "analysis": { ...AI output fields... },
  "is_duplicate": false,
  "is_correlated": false,
  "correlated_with": "",
  "confidence_score": 87,
  "next_node": ["remedy"]
}
```

---

#### `POST /tickets/approve`
Approve or reject a ticket. If approved, creates a GLPI ticket and saves to audit log.

**Request body:**
```json
{
  "ticket_id": "INC-1001",
  "category": "Network",
  "severity": "High",
  "action": "approve"
}
```

**Response:**
```json
{
  "status": "ok",
  "glpi_ticket": 42
}
```

---

### Stats

#### `GET /stats`
Returns summary metrics.

**Response:**
```json
{
  "total": 15,
  "approved": 10,
  "rejected": 5,
  "critical": 2,
  "high": 6
}
```

---

### GLPI

#### `GET /glpi/pending-review`
Returns all GLPI tickets in Pending status (4) that the agent has analyzed and are awaiting engineer review. Includes AI analysis comment and assigned team.

**Response:**
```json
[
  {
    "glpi_id": 65,
    "title": "BGP session down on Core-R1",
    "priority": 4,
    "status": 4,
    "ai_comment": "AI NOC Agent Analysis\n...",
    "assigned_team": "NOC Network Team"
  }
]
```

---

#### `POST /glpi/action`
Approve (→ Solved/5) or reject (→ Closed/6) a GLPI ticket.

**Request body:**
```json
{
  "glpi_id": 65,
  "action": "approve"
}
```

---

#### `GET /handoff/export`
Returns a multi-sheet Excel file for download.

**Sheets:**
- `Audit Log` — all processed tickets
- `Summary` — metric counts (total, approved, rejected, by severity)
- `By Category` — ticket count per category

**Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

## 12. Feature Status

### Implemented ✅

| Feature | Interface |
|---------|-----------|
| AI ticket analysis (5 categories) | All |
| Severity classification | All |
| Root cause analysis | All |
| Business impact assessment | All |
| Recommended action | All |
| Confidence scoring (0-100%) | All |
| Deduplication detection — SQLite-persisted across restarts | Streamlit, React |
| Root cause correlation | Streamlit, React |
| SLA countdown timer | Streamlit, React |
| Email template generation | Streamlit, React |
| Human-in-the-Loop approval | All |
| GLPI ticket creation on approval | Streamlit, React |
| GLPI group assigned at ticket creation (email shows group) | Streamlit, React |
| GLPI auto-analysis (background) | GLPI Agent |
| GLPI team assignment (5 groups) | GLPI Agent |
| GLPI SLA assignment | GLPI Agent |
| GLPI priority setting | GLPI Agent |
| GLPI NOC dashboard (7 widgets) | GLPI |
| GLPI email notifications (Gmail SMTP, auto cron) | GLPI |
| GLPI ITIL categories (5 types, auto-assigned) | GLPI |
| Branded email template (NOC Alert layout) | GLPI |
| Queue view with severity filters | Streamlit, React |
| Analytics dashboard — Plotly charts (6 KPIs, 6 charts, filterable audit log) | Streamlit |
| Shift handoff report | Streamlit, React |
| Excel export | Streamlit, React |
| Word document export | Streamlit |
| Persistent agent state (SQLite) | All |
| Browser push notifications | React |
| One-command startup | All |
| Cisco DNA Center connector — live device health alerts | Streamlit |
| Meraki webhook receiver — real-time alerts via FastAPI (port 8003) | Standalone |
| Data source selector — Mock CSV / DNA Center / Both | Streamlit |
| Realistic mock data — 50 unique telecom-grade alerts with syslog logs | All |
| Streamlit queue view redesigned — OpManager-style horizontal rows, always-visible, no click-to-expand | Streamlit |
| Per-row ▶ Process button — any ticket can be picked from queue, not just next in sequence | Streamlit |
| ← Back to Queue button in HITL panel — no page restart needed to return to queue | Streamlit |
| Severity filter buttons in left-side panel (st.columns([1,5]) layout) | Streamlit |
| Live SLA timer ticking during HITL review (1-second rerun loop, only active when waiting_for_user) | Streamlit |
| Auto-scan removed — engineer controls flow manually via Scan Next or per-row Process button | Streamlit |

### Pending 🔲

| Feature | Priority | Notes |
|---------|----------|-------|
| Multi-agent refactor | High | Supervisor + specialized agents + Notification agent |
| Chatbot interface | High | Natural language queries over tickets and GLPI |
| GLPI SLA escalation rules | Medium | Rules engine in GLPI |
| RAG with runbooks | Medium | Will write realistic Emircom SOPs |
| Real Remedy integration | Future | Needs IT department API access |
| Microsoft Teams/Email integration | Future | For maintenance window detection |

---

## 13. Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| Groq API rate limits (free tier) | Agent posts "unavailable" message, retries next cycle | Upgrade to paid tier or add retry delay |
| Mock data only (no real Emircom alerts) | Demonstrations use simulated incidents | Supervisor approval needed for real data |
| No real Remedy integration | GLPI used as substitute | GLPI is functionally equivalent for prototype |
| LLM analysis quality depends on log detail | Vague logs → lower confidence score | Real logs from monitoring systems will improve this |
| Python 3.14 Pydantic V1 warnings | Harmless console warnings | Upgrade Pydantic to V2 in future |
| RAG not wired in | Agent answers from training knowledge only | Wire `rag_core.py` when runbooks are available |
| Single-user (no auth) | Anyone with URL can access | Add authentication before production use |
| No auto-scan — engineer must manually trigger each ticket (intentional design for HITL control) | Engineer must click Scan Next or ▶ Process per ticket | Intentional — full engineer control over flow |

---

## 14. Future Roadmap

### Phase 2 — After Supervisor Approval

1. **Real data integration**
   - Connect to Emircom's actual monitoring system alert feed
   - Replace `mock_tickets.csv` with live data stream
   - Connect to real Remedy API

2. **RAG with real runbooks**
   - Load Emircom standard operating procedures into `data/emircom_runbooks/`
   - `rag_core.py` indexes them with BGE-M3 embeddings
   - Agent references SOPs during analysis → higher accuracy and confidence

3. **Microsoft 365 integration**
   - Read maintenance notifications from Teams channels
   - Read planned outage emails
   - Auto-create suppression rules (no alerts during planned maintenance)

4. **Auto-escalation**
   - If Critical ticket sits in Pending > 10 minutes, page the shift lead via Teams
   - SLA breach notifications to management

5. **24/7 Auto-polling mode**
   - Replace manual scan button with continuous monitoring
   - Agent watches for new alerts and queues them automatically

### Phase 3 — Production

6. **Authentication & RBAC**
   - Login system for engineers
   - Role-based access (tier-1, tier-2, shift lead, management)

7. **Network topology visualization**
   - Visual map showing affected nodes
   - Requires real infrastructure topology data

8. **Trend analysis**
   - "This device has had 12 incidents in 7 days"
   - Requires 30+ days of historical data

9. **Multilingual support**
   - Arabic interface for local engineers
   - `arabic_reshaper` and `python-bidi` already in stack

---

## 15. Changelog

**April 16, 2026:**
- Streamlit UI overhaul: queue redesigned to OpManager-style horizontal rows
- Auto-scan removed; engineers control flow via Scan Next or per-row ▶ Process button
- ← Back to Queue button added to HITL panel (no more full page restart)
- Severity filters moved to left-side panel (always visible alongside queue)
- SLA timer ticks live every second during HITL review
- Fixed int64 JSON serialization bug in save_ticket_index()
- Fixed corrupted JSON auto-recovery in load_ticket_index()
- GitHub repo pushed: YznCodeX/Emircom_NOC_Agent (main branch)

---

*Documentation last updated: April 16, 2026*  
*Project path: `C:\Users\Yazan\Desktop\Emircom_NOC_Agent`*  
*To resume in a new session: tell Claude to read `PROJECT_REPORT.md`*
