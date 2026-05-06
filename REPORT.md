# Emircom NOC Agent — Project Report
**Date:** May 6, 2026  
**Author:** Yazan  
**Role:** Final semester student, AI major — Trainee at Emircom (unpaid)  
**Supervisor:** TBD

---

## Executive Summary

This report documents the development of an AI-powered Network Operations Center (NOC) agent built for Emircom. The system was built from scratch over approximately four weeks (March 24 – April 19, 2026) as a final semester project and prototype for supervisor approval.

The agent automates the manual triage work performed by NOC engineers — classifying alerts, identifying root causes, routing tickets to the correct team, matching standard procedures, and generating shift handoff reports — while keeping engineers in control of all final decisions. The system has grown into a true multi-agent architecture: a Supervisor LLM re-classifies every alert independently before routing it to one of five specialist agents, a Runbook Agent retrieves the relevant standard operating procedure, and an Escalation Agent monitors unacknowledged tickets and pages the shift lead when thresholds are breached.

---

## 1. Background

### The Problem
Emircom's NOC operates 24/7. Engineers manually process every incoming alert:
- Read and classify the alert
- Identify which team is responsible
- Create a ticket in the Remedy ITSM system
- Send email notifications to teams
- Track SLA compliance
- Write shift handoff reports at the end of every shift

This is time-consuming, repetitive, and dependent on individual engineer experience. During high-volume periods, critical alerts can be missed or delayed.

### The Goal
Build an AI agent that handles the repetitive triage work automatically, presents its analysis to the engineer, and waits for human approval before taking action. The engineer stays in control — the agent handles the volume.

### Constraints
- No access to real Emircom data (waiting for supervisor approval)
- No access to Remedy API (requires IT department authorization)
- No Microsoft 365 API access (requires IT department authorization)
- Built on free-tier APIs (Groq) to keep costs at zero

---

## 2. What Was Built

### 2.1 Core AI Agent
The brain of the system. Built using **LangGraph** (a graph-based AI orchestration framework) with **LLaMA 3.3 70B** (via Groq API) as the language model.

The agent processes each ticket through a pipeline:
1. **Triage** — initial classification and state setup
2. **Deduplication** — detects if this alert is a repeat of a recent one (SQLite-persisted across restarts)
3. **Supervisor** *(new)* — a separate LLM independently re-classifies the alert category, overwriting the caller's label if it disagrees; stores its reasoning for transparency
4. **Specialist Analysis** — routes to one of 5 expert nodes (Network, Security, Hardware, Cloud, Application)
5. **Runbook Retrieval** *(new)* — LLM searches 13 Emircom runbooks and returns the best matching procedure with a confidence score
6. **Correlation** — checks if this ticket shares a root cause with recent tickets
7. **Human Review** — presents all findings to the engineer for approval; GLPI ticket body includes the matched runbook so other teams have a complete playbook

For every ticket, the agent produces:
- Severity level (Critical / High / Medium / Low)
- Affected node/system
- Root cause analysis
- Business impact assessment
- Recommended remediation steps
- Confidence score (0–100%)

### 2.2 Three Interfaces
The same AI agent powers three separate interfaces:

| Interface | Technology | Purpose |
|-----------|-----------|---------|
| **Streamlit** | Python, Streamlit | Original full-featured NOC dashboard — built first, most complete |
| **GLPI** | Docker, PHP, REST API | Industry-standard ITSM system — agent works on tickets submitted here |
| **React** | React, Vite, FastAPI | Modern web dashboard — intended as a commercial-grade product |

### 2.3 Features Built

#### AI Capabilities
- **Multi-agent Supervisor** — LLM re-classifies every alert before routing; catches mislabeled alerts from CSV or parser errors; stores routing reason for engineer transparency
- 5-category specialist analysis (Network, Security, Hardware, Cloud, Application)
- **Runbook Agent (RAG)** — LLM retrieves the best matching procedure from 13 Emircom runbooks; displayed in the HITL panel as a 📖 Runbook tab; confidence-scored (threshold 50%)
- **Escalation Agent** — monitors Critical (>5 min) and High (>15 min) tickets sitting unacknowledged at HITL; fires a pulsing red banner in the UI and sends an escalation email to the NOC Shift Lead; no background threads — hooks into the existing 1-second SLA rerun loop
- **NOC Chatbot** — streaming conversational interface for engineers; knows the live pending queue; engineers can paste raw logs directly into chat; scope-hardened against off-topic requests and prompt injection
- Deduplication — flags repeated alerts from same root cause (SQLite-persisted)
- Cross-ticket correlation — detects when multiple different tickets share one root cause
- Confidence scoring — agent rates its own certainty with an explanation
- Persistent memory — agent remembers context across restarts (SQLite)

#### Operational Features
- **SLA Timer** — live countdown per severity level (Critical=15min, High=1hr, Medium=4hr, Low=24hr)
- **Email Template** — auto-generated team notification email in Emircom's standard format
- **Queue View** — batch triage of all pending tickets with severity filters
- **Shift Handoff Report** — end-of-shift summary with critical incidents and watch list
- **Excel Export** — 3-sheet workbook (Audit Log, Summary, By Category)
- **Word Export** — professionally styled .docx handoff report

#### GLPI Integration
- Background agent polls GLPI every 15 seconds for new tickets
- Automatically analyzes tickets, assigns teams, sets priority, assigns SLA rules
- Posts AI analysis as a comment on the ticket
- Sets ticket to Pending status for engineer review
- 5 NOC team groups created automatically
- 4 SLA rules configured (Critical, High, Medium, Low)
- NOC dashboard with 7 widgets
- **Email notifications working** — Gmail SMTP configured, emails arrive automatically within ~1 minute
- **5 ITIL categories created** (Network, Security, Hardware, Cloud, Application) — auto-assigned on ticket creation
- **Clean email template** — branded Emircom NOC Alert with AI analysis, ticket details, and View Ticket button
- **noc.agent user** created with Gmail and added to all 5 NOC groups for notifications

#### System
- One-command startup script (`start_noc.ps1`) — starts all services automatically
- REST API backend (FastAPI) connecting React to the agent and GLPI
- Browser push notifications when GLPI tickets need review

---

## 3. Technical Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| AI Orchestration | LangGraph | Graph-based state machine — clean flow control |
| Language Model | LLaMA 3.3 70B (Groq) | Best free-tier option, fast, accurate |
| LLM SDK | Raw Groq SDK (custom shim) | `langchain_groq` deadlocks on Python 3.14; shim is a drop-in replacement |
| Runbook Retrieval | LLM 1-shot prompt (no vector DB) | No GPU available; LLM reads runbook index and picks best match directly |
| Original UI | Streamlit | Fastest way to build a working demo |
| New Frontend | React + Vite | Production-quality, reusable as a product |
| Backend API | FastAPI | Fast, automatic docs, easy to extend |
| ITSM System | GLPI (Docker) | Open-source Remedy substitute, full REST API |
| Database | SQLite (SqliteSaver) | Persistent agent memory, zero setup |
| Data Processing | Pandas | CSV and JSON handling |
| Reports | openpyxl + python-docx | Excel and Word generation |

---

## 4. Development Timeline

| Period | Milestone |
|--------|-----------|
| March 24, 2026 | Project started. Initial agent graph, Streamlit UI, mock data |
| March 25, 2026 | SLA timer, deduplication, severity escalation, email template |
| Late March 2026 | Root cause correlation, confidence scoring, multi-category routing, queue view, analytics dashboard, handoff report, Excel/Word export |
| Early April 2026 | GLPI integration — Docker setup, API connection, agent worker, team groups, SLA rules |
| April 2026 | React dashboard built — FastAPI backend, GLPI notification panel, SLA timer, email template tab, handoff report |
| April 12, 2026 | GLPI dashboard configured (7 widgets), email notifications setup started |
| April 12, 2026 (evening) | Email notifications fully working (Gmail SMTP + App Password + noc.agent user), ITIL categories created and auto-assigned, email template redesigned to clean NOC-branded layout, duplicate AI comment bug fixed |
| April 13, 2026 | Cisco DNA Center connector built (`cisco/devnet_connector.py`) — connects to Always-On DevNet sandbox, pulls live device health (CPU, memory, health score), generates alerts automatically |
| April 15, 2026 | Meraki webhook receiver built (`meraki/webhook_receiver.py` + `meraki/meraki_parser.py`) — FastAPI on port 8003, receives real Meraki alerts, runs full agent pipeline automatically. Tested end-to-end with 3 alert types (WAN down, ARP spoof, AP disconnected) → GLPI tickets created. Streamlit data source selector added (Mock CSV / DNA Center / Both). Analytics dashboard upgraded with Plotly charts (6 KPIs, donut/bar/line charts, confidence histogram, SLA breakdown, filterable audit log). Mock data completely rewritten — 50 unique telecom-grade alerts with multi-line syslog logs, Emircom device naming, cell tower and VoIP alerts. Deduplication engine upgraded to SQLite persistence — survives restarts, remembers last 10 alerts across sessions. Assigned group now set at ticket creation time — emails show correct group immediately. |
| **April 16:** | Streamlit UI overhaul — OpManager-style queue (horizontal rows, always visible), per-row ▶ Process button (pick any ticket from queue), ← Back to Queue button (no page restart), severity filters in left panel, live SLA timer during HITL review, auto-scan removed for full engineer control, int64 + JSON recovery bug fixes. GitHub repo pushed to YznCodeX/Emircom_NOC_Agent (main branch). |
| **April 18:** | **Multi-agent Supervisor node** — LLM re-classifies every alert before routing; verified override of mislabeled alerts (92% confidence). **NOC Chatbot** — streaming output, sliding window memory, live queue context, Paste Logs, scope guardrails (two-pass hardened against injection and role-play). **Python 3.14 fix** — replaced `langchain_groq` with raw Groq SDK shim (`_LazyLLM`). **Runbook Agent (RAG)** — `rag_core.py` rewritten (no GPU); 13 realistic Emircom runbooks written; `runbook_node` wired into graph; 📖 Runbook tab added to HITL panel; verified match rates: OSPF 98%, UPS 95%, DB timeout 95%, PSU 92%. **Escalation Agent** — `escalation_agent.py` built; Critical >5 min and High >15 min trigger pulsing red banner + escalation email to Shift Lead; live-tested on Cell Tower ticket INC-3812. **GLPI enrichment** — GLPI ticket body now includes matched runbook + Supervisor routing reason so other teams have a full playbook. |
| **April 19:** | **app.py refactored into 6 modules** — 1,767-line monolith split into `app.py` (969 lines), `persistence.py`, `constants.py`, `helpers.py`, `reports.py`, `chatbot.py`. **30 new mock tickets** — INC-3051–INC-3080 across all 5 categories; queue now 80 tickets. **Reports enhanced** — Word report gains SLA Compliance Rate, Avg Response Time, Avg Confidence, Severity Breakdown table; Excel Audit Log adds human-readable `Response_Time` column. **Module docstrings** — each module has a full explanation at the top. |

---

## 5. Current Status

### What Works Today
Everything listed in Section 2 is functional and has been tested. The system can:
- Accept mock NOC tickets and route them through a full multi-agent pipeline
- Re-classify alerts using an independent Supervisor LLM before routing
- Analyze alerts with AI across all 5 specialist categories
- Retrieve the matching standard operating procedure from 13 runbooks
- Present all findings to an engineer in a structured HITL panel (4 tabs: Summary, Logs, Runbook, Email)
- Escalate unacknowledged Critical/High tickets automatically — banner in UI + email to Shift Lead
- Create GLPI tickets on approval with correct team, priority, SLA, runbook, and routing reason
- Generate shift handoff reports and export to Excel and Word
- Answer engineer questions via a streaming NOC Chatbot with live queue context
- Notify engineers when GLPI tickets need review

### What Is Pending
| Item | Reason Pending |
|------|---------------|
| Real Emircom runbooks | Supervisor needs to provide SOPs — drop JSON files in `data/emircom_runbooks/`, no code changes needed |
| GLPI SLA escalation rules | Not yet configured in GLPI rules engine |
| Real Remedy connection | Waiting for IT department API access |
| Microsoft Teams/Email integration | Waiting for IT department authorization |

### Recently Completed
| Item | Date |
|------|------|
| app.py refactored into 6 focused modules (persistence, constants, helpers, reports, chatbot) | April 19, 2026 |
| 30 new mock tickets added — INC-3051–INC-3080 (queue now 80 tickets) | April 19, 2026 |
| Reports enhanced — SLA compliance %, avg response time, severity breakdown table, Excel Response_Time column | April 19, 2026 |
| Module docstrings — full architectural explanation at top of each streamlit module | April 19, 2026 |
| Multi-agent Supervisor node — independent alert re-classification | April 18, 2026 |
| NOC Chatbot — streaming, queue context, Paste Logs, scope guardrails | April 18, 2026 |
| Runbook Agent (RAG) — 13 runbooks, LLM retrieval, HITL Runbook tab | April 18, 2026 |
| Escalation Agent — pulsing banner + email to Shift Lead for overdue HITL tickets | April 18, 2026 |
| GLPI ticket enrichment — runbook + supervisor reason in ticket body | April 18, 2026 |
| GitHub repo pushed (YznCodeX/Emircom_NOC_Agent, main branch) | April 16, 2026 |

---

## 6. Challenges and Solutions

| Challenge | Solution |
|-----------|---------|
| No access to real Emircom data | Built 80 unique telecom-grade mock tickets with real syslog logs covering all incident types (INC-3001–INC-3080) |
| No Remedy API access | Used GLPI (open-source ITSM) as a fully functional substitute |
| Groq API rate limits on free tier | Added graceful error handling — clean message posted to ticket, retried next cycle |
| Double-processing tickets | `has_real_ai_comment()` check prevents re-analysis |
| GLPI only watching "New" tickets | Updated to also watch "Processing" (manually created tickets default to this status) |
| Agent import broken after code reorganization | Fixed with `sys.path.insert` to locate `src/` from any subfolder |
| `langchain_groq` hangs on Python 3.14 | Replaced with raw Groq SDK shim (`_LazyLLM`) — exposes the same `.invoke()` interface, zero deadlocks |
| RAG with no GPU and no vector DB | Replaced embedding-based retrieval with a single LLM prompt that reads the runbook index and picks the best match directly — faster, simpler, equally accurate |
| Escalation without background threads | Streamlit is single-threaded; escalation check piggybacks on the existing 1-second SLA rerun loop — no new threads or dependencies |
| Engineers sending wrong emails at 3am | Escalation email fires only once per ticket (`escalation_sent` session state flag), regardless of how many reruns happen after the threshold |

---

## 7. Next Steps

### Immediate (Presentation Prep)
1. Slack integration — post Critical approvals to a team channel (30 min, high demo value)
2. Demo rehearsal — walk through full pipeline: alert in → Supervisor routes → Runbook matched → Escalation fires → GLPI ticket created → Slack notification
3. Written report formatting (ST04/COOP requirements)

### After Supervisor Approval
4. Connect to real alert feed from Emircom monitoring systems (replace mock CSV)
5. Integrate with real Remedy API (replace GLPI simulation)
6. Load real Emircom runbooks into `data/emircom_runbooks/` — no code changes needed, RAG is already wired
7. Request Microsoft 365 API access for Teams/email maintenance window detection
8. Add authentication and role-based access control (login system for engineers)

---

## 8. How to Run

```powershell
# Start all services with one command
.\start_noc.ps1
```

| Service | URL |
|---------|-----|
| React Dashboard | http://localhost:5173 |
| GLPI | http://localhost (login: glpi / glpi) |
| API Documentation | http://localhost:8001/docs |
| Streamlit Dashboard | http://localhost:8501 |

```powershell
# Push test tickets to GLPI
.\venv\Scripts\python.exe glpi\push_to_glpi.py
```

---

## 9. Notes for Next Session

- **React dashboard is fully complete** — run `cd frontend && npm run dev` (port 5173) + `uvicorn react.backend.main:app --port 8001 --reload`
- All major AI agents are live: Supervisor, Runbook, Escalation, Chatbot
- `streamlit/app.py` split into 5 sibling modules (persistence, constants, helpers, reports, chatbot) — use flat imports to avoid package name collision
- Real runbooks → drop JSON files in `data/emircom_runbooks/` — RAG is wired, no code changes needed
- Mock queue is 80 tickets (INC-3001–INC-3080); reset `data/session_state.json` to `{"ticket_index": 0}` to start from beginning
- Escalation emails go to `SHIFT_LEAD_EMAIL` env var
- `langchain_groq` must NOT be used — deadlocks on Python 3.14; use `_LazyLLM` shim from `agent_graph.py`
- Full technical documentation is in `PROJECT_REPORT.md`
- GitHub repo: YznCodeX/Emircom_NOC_Agent (main branch)

---

*Report will be updated as the project progresses.*  
*Last updated: May 6, 2026 (v1.6)*
