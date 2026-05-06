# Emircom NOC Agent — Project Progress

## About the Project
An AI-powered NOC (Network Operations Center) agent built to automate what the NOC department at Emircom does manually. Built by Yazan — final semester student, AI major, trainee at Emircom (unpaid). This is a prototype to present to his supervisor to get approval and eventually access to real data and systems.

**Stack:**
- `LangGraph` — agent orchestration (graph-based state machine)
- `Groq + LLaMA 3.3 70B` — the AI brain (raw Groq SDK shim; `langchain_groq` hangs on Python 3.14)
- `Streamlit` — the UI (NOC Command Center dashboard)
- `SqliteSaver` — persistent agent state
- `src/rag_core.py` — LLM-based runbook retrieval over 13 JSON runbooks (wired and live)

---

## What the Agent Does (Core Flow)

```
Incoming Ticket
      ↓
   Triage
      ↓
 Deduplication ──── (duplicate?) ──→ Drop Node → HITL (approve drop)
      ↓
 Supervisor Node  ← LLM re-classifies category (overwrites caller's label)
      ↓
 Network/Security/Hardware/Cloud/Application Ops (LLM specialist analysis)
      ↓
 Runbook Node  ← LLM matches alert to 1 of 13 runbooks
      ↓
 Correlation Engine (root cause linking)
      ↓
 Remedy Node → HITL (approve/reject) → GLPI ticket (with runbook + supervisor reason)
      ↓
   END
```

**HITL = Human-in-the-Loop** — agent pauses before Remedy and Drop, waits for engineer to Approve or Reject.

---

## Context About Emircom's NOC

- NOC operates 24/7 with shift rotations
- Yazan only observed 4 hours/day as a trainee so only saw ~5-6 tickets, but full day volume is likely much higher
- Engineers use **Remedy** as their ITSM system for ticket creation and assignment
- When responsible team is unknown or external → engineer manually sends an **email using a table-format template** (only one template used)
- They almost always know which team to assign to in Remedy
- Some tickets are ignored because of planned maintenance, site relocations, or known outages — engineers get notified via **email or Microsoft Teams**
- Engineers communicate via **Teams and email**

---

## Enhancements — Completed

### ✅ #1 — Persistent State (SqliteSaver)
**File:** `src/agent_graph.py`
- Replaced `MemorySaver` with `SqliteSaver`
- Agent state written to `data/noc_memory.db`
- App restart no longer wipes agent memory

**File:** `app.py`
- `processed_tickets` loads from `data/processed_tickets.json` on startup
- Saves to JSON after every Approve/Reject
- `ticket_index` loads from `data/session_state.json` on startup
- Saves after every ticket advance, resets to 0 when all tickets processed

### ✅ Bug Fix — CSV Column Mismatch
**File:** `data/mock_tickets.csv`
- Root cause: `Raw_Logs` field had unquoted commas → pandas auto-used `Ticket_ID` column as row index → all columns shifted
- Fix: quoted all `Raw_Logs` fields with commas
- Result: `ticket["Ticket_ID"]` now correctly returns `INC-1001`, not `Network`

### ✅ Bug Fix — Wrong Category in Audit Log
**File:** `app.py`
- Added `original_category` to session state — stores the CSV category (Network/Security) when ticket is picked up
- Approve and Reject now save `original_category` instead of the AI-analyzed sub-category

### ✅ #2 — SLA Tracking
**File:** `app.py`
- SLA thresholds: Critical=15min, High=1hr, Medium=4hr, Low=24hr
- Timer starts the moment HITL panel appears
- UI shows: green (on track), yellow (≥75% elapsed), red (breached)
- Progress bar: `Elapsed: Xm Xs / Limit: Ym`
- `Response_Time_Secs` and `SLA_Breached` saved in audit log
- Analytics dashboard has SLA Breached metric tile

### ✅ #3 — Better Error Handling in Deduplication
**File:** `src/agent_graph.py`
- Replaced bare `except:` with two specific handlers:
  - `json.JSONDecodeError` — LLM returned bad JSON, logs raw response
  - `Exception` — API/network failure, logs error type and message
- `duplicate_reason` carries `DEDUP_WARN` or `DEDUP_ERROR` prefix when something went wrong
- UI shows warning banner if dedup failed silently

### ✅ #4 — Severity Escalation Logic + Remedy Simulation + Email Template
**File:** `app.py`
- Team routing based on category:
  - Network → Network Operations Team (`network-ops@emircom.com`)
  - Security → Security Operations SOC (`soc-team@emircom.com`)
  - Unknown → NOC Tier-2 (`noc-support@emircom.com`)
- Escalation panel appears for every non-duplicate ticket:
  - **Critical** → Remedy ticket number + team + "On-Call Page SENT" + bridge call notification
  - **High** → Remedy ticket + team + "Team Lead Notified"
  - **Medium/Low** → Remedy ticket + team, no escalation noise
- Auto-generated email template (table format, matches Emircom style) with all ticket data pre-filled
- Remedy ticket number format: `REM-{ticket_number}-{HHMM}`

### ✅ #5 — Root Cause Correlation
**File:** `src/agent_graph.py`
- Added `is_correlated` and `correlated_with` to `AgentState`
- Added `correlation_cache` — stores last 10 analyzed tickets
- Added `correlation_node` — LLM checks if current ticket shares root cause with recent ones
- Graph: `network_ops → correlation → remedy`, `security_ops → correlation → remedy`
- Full error handling for JSON parse and API failures

**File:** `app.py`
- Orange warning banner in HITL panel when correlation detected: "This ticket may share root cause with INC-XXXX"
- `Correlated_With` field saved in audit log

---

### ✅ #7 — Confidence Scoring
**File:** `src/agent_graph.py`
- All 5 analysis nodes (`network_ops`, `security_ops`, `hardware_ops`, `cloud_ops`, `application_ops`) return `Confidence_Score` (0–100) and `Confidence_Reason`
- Score extracted from JSON and stored in `AgentState.confidence_score`

**File:** `app.py`
- HITL panel shows a progress bar: ✅ High (≥85%), ⚠️ Moderate (60–84%), 🔴 Low (<60%)
- `Confidence_Reason` shown as caption below the bar
- `Confidence_Score` saved in audit log

### ✅ #8 — Multi-category Routing
**File:** `src/agent_graph.py`
- Added `hardware_ops_node` — Field Engineering prompt (PSU, transceiver, disk, fan faults)
- Added `cloud_ops_node` — Cloud Infrastructure prompt (VM, datastore, auto-scaling)
- Added `application_ops_node` — App Support prompt (crashes, DB timeouts, auth failures)
- `route_after_dedup` uses `CATEGORY_ROUTING` dict for all 5 categories
- All 3 new nodes feed into `correlation → remedy`

**File:** `app.py`
- `TEAM_ROUTING` expanded:
  - Hardware → Field Engineering Team (`field-eng@emircom.com`)
  - Cloud → Cloud Infrastructure Team (`cloud-ops@emircom.com`)
  - Application → Application Support Team (`app-support@emircom.com`)

**File:** `data/mock_tickets.csv`
- Added INC-1065 to INC-1074: 4 Hardware, 3 Cloud, 3 Application tickets with realistic logs

---

### ✅ Python 3.14 / langchain_groq Fix — Raw Groq SDK Shim
**File:** `src/agent_graph.py`
- `langchain_groq` deadlocked on Python 3.14.3 (Pydantic V1 incompatibility)
- Replaced with `_LazyLLM` shim — wraps raw `groq.Groq` client
- Exposes `.invoke(prompt)` → returns object with `.content` attribute (drop-in replacement)
- All nodes, chatbot, and RAG retrieval use the same shim

### ✅ Multi-agent Supervisor Node
**File:** `src/agent_graph.py`
- Added `supervisor_node()` — LLM reads `description` + `logs`, classifies category independently
- Overwrites caller-provided `state["category"]` with its own classification
- Stores classification reason in `state["supervisor_reason"]`
- Added `supervisor_reason: str` to `AgentState`
- Changed `route_after_dedup()` to route all unique tickets to `supervisor` instead of directly to specialists
- Added `route_after_supervisor()` — reads LLM-set category, routes to correct specialist node
- Verified: Network alert mislabeled as Application → Supervisor overrides to Network (92% confidence)
- All 3 callers (Streamlit, GLPI agent, Meraki webhook) unchanged

### ✅ NOC Chatbot
**File:** `streamlit/app.py`
- New Tab 4 — full streaming chat interface for NOC engineers
- Streaming via `st.write_stream` — token-by-token output
- Sliding window memory — last 10 conversation turns kept in system context
- Paste Logs button — populates chat input with last raw log from pending queue
- System prompt includes live pending queue (ticket IDs, categories, descriptions)
- Scope guardrails: blocks off-topic requests, prompt injection, role-play jailbreaks
- Two-pass hardening: v1 blocked haiku attempts, v2 blocked persona override attacks
- Live-tested: streaming, queue retrieval, log paste, cascade analysis, Arabic, hallucination probe, injection resistance

### ✅ #11 — Queue View (OpManager-style Ticket Board)
**File:** `app.py`
- Added 3rd tab: **📡 Queue View** alongside existing Live Operations and Analytics tabs
- `get_processed_ids()` — returns set of already-processed Ticket_IDs for fast lookup
- `get_pending_tickets()` — filters full CSV to only unprocessed tickets
- `batch_scan_queue()` — single LLM call to AI-triage all pending tickets at once:
  - Returns per-ticket: `severity`, `alert_type`, `summary`, `group` (device/service/security/cloud)
  - Falls back gracefully if LLM returns bad JSON
- Left sidebar filter panel with severity buttons showing live counts: All / Critical / High / Medium / Low
- Ticket rows display: severity icon (🔴🟠🟡🔵), Ticket ID, alert type icon, AI summary, ✅ Approve / ❌ Reject inline buttons
- Inline Approve/Reject immediately saves to `processed_tickets.json`, advances `ticket_index`, reruns UI
- `analyze_current_ticket()` updated with skip logic — auto-advances past any ticket approved/rejected from Queue View
- Confidence_Score saved as `str` in audit log to avoid PyArrow mixed-type errors in Analytics dataframe

**Tested results (40 mock tickets):**
- All (40), Critical (5), High (16), Medium (17), Low (2)
- Critical filter shows: INC-1842 (RADIUS Unreachable), INC-1065 (PSU Failure), INC-1070 (NFS Datastore Latency), INC-1072 (NOC Web Portal 502), INC-1074 (API Auth Down)

---

### ✅ Runbook Agent (RAG)
**Files:** `src/rag_core.py` (full rewrite), `src/agent_graph.py`, `data/emircom_runbooks/` (13 new JSON files), `streamlit/app.py`

**rag_core.py:**
- Old version used HuggingFace BGE-M3 on CUDA — not compatible with Python 3.14, no GPU available
- New version: LLM-based retrieval — builds a one-line index of all runbook IDs/titles/triggers, sends 1-shot prompt to LLM, gets back `{match_index, confidence, reason}` JSON
- Confidence threshold: 50% — below this returns "" (no match shown)
- Verified match rates: OSPF → 98%, UPS → 95%, DB timeout → 95%, PSU failure → 92%

**13 runbooks written (fake Emircom SOPs):**
- Network: RB-NET-001 (OSPF), RB-NET-002 (BGP), RB-NET-003 (Interface Flapping), RB-NET-004 (MPLS), RB-NET-005 (Cell Tower/BTS), RB-NET-006 (High Bandwidth)
- Hardware: RB-HW-001 (UPS Battery), RB-HW-002 (High CPU/Temperature)
- Security: RB-SEC-001 (IDS Alert), RB-SEC-002 (Brute Force)
- Cloud: RB-CLD-001 (VM/Container Crash)
- Application: RB-APP-001 (DB Timeout), RB-APP-002 (Web Service 502)

**agent_graph.py:**
- Added `runbook_match: str` to `AgentState`
- Added `runbook_node()` — calls `find_matching_runbook()` with description, logs, category, llm
- Added `workflow.add_node("runbook", runbook_node)`
- All 5 specialist nodes now route to `runbook` before `correlation`

**app.py:**
- HITL panel now has 4 tabs: Summary, Raw Logs, 📖 Runbook, Email Template
- Runbook tab renders matched procedure in markdown; shows confidence %, steps, resolution, escalation path
- Supervisor routing reason shown as caption below runbook

### ✅ Escalation Agent
**Files:** `src/escalation_agent.py` (new file), `streamlit/app.py`

**escalation_agent.py:**
- `check_escalation(severity, sla_start_time, already_escalated) → dict` — computes elapsed vs threshold
- `send_escalation_email(...)` — branded HTML email via Gmail SMTP (port 587, STARTTLS)
- Thresholds: Critical → 5 min, High → 15 min, Medium → 45 min (Medium: banner only, no email)
- Uses same `GMAIL_USER` / `GMAIL_APP_PASSWORD` env vars as existing email sender

**app.py:**
- Escalation check runs on every 1s SLA-timer rerun (no background threads)
- `escalation_sent` session state flag → email fires exactly once per ticket
- Flag reset in 3 places: new ticket start, Back to Queue, _save_and_advance()
- Pulsing red CSS banner displayed when threshold breached
- Quieter dark-red "already escalated" reminder shown on subsequent reruns
- Live-tested: banner appeared within 10s on Critical Cell Tower ticket INC-3812

### ✅ GLPI Ticket Enrichment (Runbook + Supervisor Reason)
**File:** `src/agent_graph.py` — `remedy_node()`
- GLPI ticket body now appends matched runbook procedure + Supervisor routing reason
- `_plain()` helper strips markdown bold/italic before writing to GLPI (plain-text field)
- Other teams (field engineers, security, etc.) see the complete SOPwhen they open the ticket in GLPI
- No changes to GLPI API calls — enrichment is purely in the `description` field

---

### ✅ React Dashboard — Full Port (May 2026)
**Files:** `frontend/src/` (pages + components) + `react/backend/main.py`

Complete React + Vite frontend built across 6 stages:

**Stage 1 — Foundation**
- React Router v7 with sidebar `Navbar` and 5 routes: `/`, `/operations`, `/analytics`, `/chatbot`, `/reports`
- Shared components: `SeverityBadge`, `StatCard`, `SLATimer`, `TicketRow`, `GLPINotificationPanel`
- `constants.js` (SEV_COLORS, CAT_ICONS, SLA_MINUTES) + `utils.js` (generateEmailTemplate)

**Stage 2 — Dashboard Banners**
- Shift Briefing banner (blue) — LLM-generated queue summary on load via `GET /shift-briefing`
- Trend Analysis banner (amber) — LLM pattern detection via `GET /trend-analysis` after each ticket action

**Stage 3 — Live Operations Page**
- 2-step approval wizard: Step 1 (Approve/Reject) → Step 2 (email confirmation card with severity-colored border, Send/Skip)
- Escalation banner: pulsing red when Critical >5min or High >15min unacknowledged
- Duplicate/correlation banners from agent response flags
- 4 tabs: Summary / Raw Logs / 📖 Runbook / ✉️ Email Template

**Stage 4 — Analytics Page**
- 6 KPI cards: Total, Approved, Rejected, Critical, Avg Confidence, SLA Compliance %
- 6 Recharts charts: category donut, severity bar, status-by-category stacked bar, confidence histogram, SLA grouped bar, ticket volume bar
- Filterable audit log (Category / Severity / Status dropdowns)
- PIR download section (lists files from `data/pir/`)

**Stage 5 — Chatbot Page**
- SSE streaming via `GET /chatbot/stream?message=...` FastAPI endpoint
- 6 suggestion chips with pure-Python structured answers (bypasses LLM verbosity)
- Paste Logs toggle, 10-turn history trimming, auto-scroll, blinking cursor while streaming
- System prompt: last 30 processed + full pending queue injected fresh each call

**Stage 6 — Reports Page**
- Shift Handoff form (3 inputs) + Generate Report + Excel download
- PIR list: fetches `GET /pir/list`, renders each `.docx` with `📥 Download` button

**New backend endpoints added:**
- `GET /shift-briefing` — LLM shift summary
- `GET /trend-analysis` — LLM trend detection
- `GET /chatbot/stream` — SSE streaming
- `GET /pir/list` — lists PIR files
- `GET /pir/download/{ticket_id}` — serves PIR .docx
- Fixed: missing `datetime` import (broke `/handoff/export`)

---

## Enhancements — Remaining (In Priority Order)

### 🔲 Slack Integration
Post Critical ticket approvals to a Slack channel via incoming webhook. ~30 min effort, high demo value.

### 🔲 Trend Analysis
"This IP has had 12 incidents in the last 7 days." Needs historical data to be meaningful — better to build after getting real data.

### 🔲 Network Topology Map
Visual map showing which nodes are affected. Most complex to build, needs real infrastructure data. Save for after supervisor approval.

---

## Future Features (Post-Supervisor Approval)

These were discussed but intentionally NOT built yet — waiting for real data and system access:

### 🔮 Real Runbooks
`data/emircom_runbooks/` is ready with 13 fake SOPs wired to the LLM retrieval engine. When real Emircom runbooks are provided, drop JSON files in — no code changes needed.

### 🔮 Maintenance Window / Suppression Rules
When a planned maintenance, site relocation, or known outage is scheduled, alerts from affected devices should be automatically suppressed (no SLA, no escalation, logged as "Planned Maintenance").

### 🔮 Real Email & Teams Integration (Microsoft 365 API)
Agent reads maintenance notifications from Teams channels and emails, automatically creating suppression rules. Requires IT department approval and Microsoft 365 API credentials.

### 🔮 Real Remedy API Integration
Currently simulated with GLPI. Replace with actual Remedy API calls to create tickets, assign teams, and track status. Requires Remedy API access from Emircom IT.

### 🔮 Enhanced Escalation
Escalation Agent is live for HITL overdue tickets. Next level: escalate via Teams message + auto-advance ticket if shift lead doesn't respond within a second threshold.

### 🔮 Knowledge Base Agent
Learns from past approved tickets. When new alert arrives, checks if similar ticket existed: "Similar to INC-3033 last shift — here's what the engineer did."

---

## Important Technical Notes

- **Python version:** 3.14 (causes Pydantic V1 warnings — harmless, just warnings)
- **Groq SDK:** Using raw `groq.Groq` via `_LazyLLM` shim — `langchain_groq` deadlocks on Python 3.14
- **Groq model:** `llama-3.3-70b-versatile` at temperature 0.1
- **LangGraph interrupts:** `interrupt_before=["remedy", "drop"]` — pauses before both actions
- **SqliteSaver connection:** `check_same_thread=False` required for Streamlit
- **CSV quirk:** Always quote fields with commas in `mock_tickets.csv`
- **Escalation emails:** `GMAIL_APP_PASSWORD` env var required; `SHIFT_LEAD_EMAIL` defaults to same Gmail box if not set
- **Runbook matching:** LLM 1-shot retrieval; confidence < 50% returns ""; real runbooks → drop JSON into `data/emircom_runbooks/`

---

## Data Files
| File | Purpose |
|---|---|
| `data/mock_tickets.csv` | 50 unique telecom-grade alerts with syslog logs |
| `data/noc_memory.db` | SqliteSaver agent state (LangGraph checkpoints + dedup table) |
| `data/processed_tickets.json` | Audit log of all processed tickets |
| `data/session_state.json` | Persists ticket_index across restarts |
| `data/emircom_runbooks/` | 13 JSON runbooks — LLM-based retrieval wired and live |

---

## How to Run
```bash
# Activate venv
venv/Scripts/activate

# Run the app
streamlit run app.py
```
App opens at `http://localhost:8501`

---

## To Resume in a New Chat
Tell Claude: **"Read PROGRESS.md in my project folder at C:\Users\Yazan\Desktop\Emircom_NOC_Agent"**
Then say what you want to work on next.
