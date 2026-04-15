# Emircom NOC Agent — Project Report
**Date:** April 12, 2026  
**Author:** Yazan  
**Role:** Final semester student, AI major — Trainee at Emircom (unpaid)  
**Supervisor:** TBD

---

## Executive Summary

This report documents the development of an AI-powered Network Operations Center (NOC) agent built for Emircom. The system was built from scratch over approximately 3 weeks (March 24 – April 12, 2026) as a final semester project and prototype for supervisor approval.

The agent automates the manual triage work performed by NOC engineers — classifying alerts, identifying root causes, routing tickets to the correct team, and generating shift handoff reports — while keeping engineers in control of all final decisions.

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
1. **Triage** — initial classification
2. **Deduplication** — detects if this alert is a repeat of a recent one
3. **Specialist Analysis** — routes to one of 5 expert nodes (Network, Security, Hardware, Cloud, Application)
4. **Correlation** — checks if this ticket shares a root cause with recent tickets
5. **Human Review** — presents findings to engineer for approval

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
- 5-category specialist analysis (Network, Security, Hardware, Cloud, Application)
- Deduplication — flags repeated alerts from same root cause
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
| Embeddings | BGE-M3 | Ready for RAG when real runbooks available |
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

---

## 5. Current Status

### What Works Today
Everything listed in Section 2 is functional and has been tested. The system can:
- Accept mock NOC tickets
- Analyze them with AI across all 5 categories
- Present findings to an engineer for review
- Create GLPI tickets on approval with correct team, priority, and SLA
- Generate shift handoff reports and export to Excel
- Notify engineers when GLPI tickets need review

### What Is Pending
| Item | Reason Pending |
|------|---------------|
| Multi-agent refactor | Planned Week 2 |
| Chatbot interface | Planned Week 2 |
| GLPI SLA escalation rules | Not yet configured |
| RAG with runbooks | No real Emircom runbooks available — will write realistic SOPs |
| Real Remedy connection | Waiting for IT department API access |
| Microsoft Teams/Email integration | Waiting for IT department authorization |

---

## 6. Challenges and Solutions

| Challenge | Solution |
|-----------|---------|
| No access to real Emircom data | Built 40+ realistic mock tickets covering all incident types |
| No Remedy API access | Used GLPI (open-source ITSM) as a fully functional substitute |
| Groq API rate limits on free tier | Added graceful error handling — clean message posted to ticket, retried next cycle |
| Double-processing tickets | `has_real_ai_comment()` check prevents re-analysis |
| GLPI only watching "New" tickets | Updated to also watch "Processing" (manually created tickets default to this status) |
| Agent import broken after code reorganization | Fixed with `sys.path.insert` to locate `src/` from any subfolder |
| Architecture confusion (GLPI vs React flow) | Clarified: CSV → Agent → Approve → GLPI ticket. React and GLPI are separate interfaces, same agent |

---

## 7. Next Steps

### Week 2 (Next)
1. Multi-agent refactor — Supervisor agent + specialized agents + Notification agent
2. Chatbot — natural language queries over processed tickets and GLPI data

### Week 3
3. React analytics tab improvements
4. RAG runbooks — write realistic Emircom SOPs, wire into agent
5. GLPI SLA escalation rules

### Week 4 (Buffer)
6. Supervisor presentation prep and demo rehearsal
7. Written report formatting (ST04 requirements)

### After Supervisor Approval
8. Connect to real alert feed from Emircom monitoring systems
9. Integrate with real Remedy API
10. Load real Emircom runbooks into RAG system
11. Request Microsoft 365 API access for Teams/email integration
12. Add authentication and role-based access control

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

- Email pipeline fully working — no manual steps needed, emails arrive automatically within ~1 minute
- GLPI categories (Network, Security, Hardware, Cloud, Application) created and auto-assigned via API
- React analytics tab is the next major frontend feature to build
- Supervisor presentation prep should start soon
- Full technical documentation is in `PROJECT_REPORT.md`

---

*Report will be updated as the project progresses.*  
*Last updated: April 15, 2026*
