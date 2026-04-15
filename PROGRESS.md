# Emircom NOC Agent — Project Progress

## About the Project
An AI-powered NOC (Network Operations Center) agent built to automate what the NOC department at Emircom does manually. Built by Yazan — final semester student, AI major, trainee at Emircom (unpaid). This is a prototype to present to his supervisor to get approval and eventually access to real data and systems.

**Stack:**
- `LangGraph` — agent orchestration (graph-based state machine)
- `Groq + LLaMA 3.3 70B` — the AI brain (via `langchain_groq`)
- `Streamlit` — the UI (NOC Command Center dashboard)
- `SqliteSaver` — persistent agent state
- `BGE-M3` embeddings in `rag_core.py` — ready but not wired in yet (waiting for real runbook data)

---

## What the Agent Does (Core Flow)

```
Incoming Ticket
      ↓
   Triage
      ↓
 Deduplication ──── (duplicate?) ──→ Drop Node → HITL (approve drop)
      ↓
 Network/Security Ops (LLM Analysis)
      ↓
 Correlation Engine (root cause linking)
      ↓
 Remedy Node → HITL (approve/reject)
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

## Enhancements — Remaining (In Priority Order)

### 🔲 #6 — Real-time Alert Feed (Auto-refresh)
Instead of manually clicking "Start NOC Auto-Scan", the dashboard auto-refreshes every N seconds to check for new tickets. Makes it feel live instead of a demo.

### 🔲 #9 — Trend Analysis
"This IP has had 12 incidents in the last 7 days." Needs historical data to be meaningful — better to build after getting real data.

### 🔲 #10 — Network Topology Map
Visual map showing which nodes are affected. Most complex to build, needs real infrastructure data. Save for after supervisor approval.

---

## Future Features (Post-Supervisor Approval)

These were discussed but intentionally NOT built yet — waiting for real data and system access:

### 🔮 Maintenance Window / Suppression Rules
When a planned maintenance, site relocation, or known outage is scheduled, alerts from affected devices should be automatically suppressed (no SLA, no escalation, logged as "Planned Maintenance").

**Planned approach:**
- Phase 1 (now): Manual suppression rule entry in UI
- Phase 2 (after approval): Agent reads Microsoft Teams messages and emails to auto-create suppression rules
- Phase 3 (ideal): Full Microsoft 365 API integration

### 🔮 Real Email & Teams Integration (Microsoft 365 API)
Agent reads maintenance notifications from Teams channels and emails, automatically creating suppression rules. Requires IT department approval and Microsoft 365 API credentials.

### 🔮 Real Remedy API Integration
Currently simulated. Replace with actual Remedy API calls to create tickets, assign teams, and track status. Requires Remedy API access from Emircom IT.

### 🔮 RAG with Real Runbooks
`src/rag_core.py` is ready with BGE-M3 embeddings. `data/emircom_runbooks` is empty. When real runbook documents are available, wire the RAG into the agent so it can reference standard operating procedures during analysis.

### 🔮 24/7 Auto-polling Mode
Replace the manual "Start NOC Auto-Scan" button with continuous auto-polling. Agent watches for new tickets and processes them automatically. Architecture depends on where real tickets come from (API, database, file feed, etc.).

### 🔮 Auto-escalation Timer
If a Critical ticket sits unapproved in HITL for X minutes, automatically escalate it — page the shift lead, send a Teams message, etc.

### 🔮 Fake Email + Fake Teams UI (Demo Enhancement)
For a more impressive demo: build a simulated inbox and Teams channel UI inside the app, where maintenance notifications appear as fake messages. The agent reads these and auto-creates suppression rules. Supervisor can see the full workflow visually.

---

## Important Technical Notes

- **Python version:** 3.14 (causes Pydantic V1 warnings — harmless, just warnings)
- **Groq API:** Using `llama-3.3-70b-versatile` at temperature 0.1
- **LangGraph interrupts:** `interrupt_before=["remedy", "drop"]` — pauses before both actions
- **SqliteSaver connection:** `check_same_thread=False` required for Streamlit
- **CSV quirk:** Always quote fields with commas in `mock_tickets.csv`
- **Streamlit deprecation warning:** `use_container_width` → use `width='stretch'` or `width='content'`

---

## Data Files
| File | Purpose |
|---|---|
| `data/mock_tickets.csv` | 4 mock tickets for demo (INC-1001 to INC-1004) |
| `data/noc_memory.db` | SqliteSaver agent state (LangGraph checkpoints) |
| `data/processed_tickets.json` | Audit log of all processed tickets |
| `data/session_state.json` | Persists ticket_index across restarts |
| `data/emircom_runbooks` | Empty — waiting for real runbook data |

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
