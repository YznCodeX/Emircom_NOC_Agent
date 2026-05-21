# Emircom NOC Agent — Project Overview
**Trainee:** Yazan  
**Organization:** Emircom (Saudi Arabia)  
**Program:** B.Sc. Artificial Intelligence — Final Semester COOP Internship  
**University:** Prince Mohammad Bin Fahd University (UPM)  
**Duration:** [Start Date] – [End Date]  
**Report Date:** May 2026

---

## I. Executive Summary

The **Emircom NOC Agent** is an AI-powered Network Operations Center (NOC) triage system built during a final-semester COOP internship at Emircom. The system automates the manual triage work performed by NOC engineers — receiving alerts, classifying severity, identifying root causes, detecting duplicates, routing to the right team, creating ITSM tickets, and sending email notifications — while keeping engineers in control of every final decision through a Human-in-the-Loop (HITL) architecture.

The system is a working prototype, demonstrated using 80 realistic telecom-grade mock alerts and an open-source ITSM platform (GLPI) as a substitute for Emircom's production Remedy system. It uses a state-of-the-art large language model (LLaMA 3.3 70B via Groq) orchestrated by LangGraph, a graph-based AI agent framework.

---

## II. Training Organization — Emircom

Emircom is a Saudi-based telecommunications and IT managed services company serving enterprise clients across the region. Its Network Operations Center operates 24 hours a day, 7 days a week, monitoring network infrastructure, security events, hardware health, cloud services, and business applications for its clients.

**NOC Manual Workflow (Before This Project):**
1. An alert fires from a monitoring system (e.g., SolarWinds, Zabbix, or Cisco DNA Center)
2. An engineer reads the alert and classifies its severity (Critical / High / Medium / Low)
3. The engineer identifies the responsible team and creates a ticket in Remedy (the ITSM system)
4. If the responsible team is external or unknown, the engineer sends a formatted email notification
5. The engineer tracks whether the SLA deadline is being met
6. At the end of a shift, the outgoing engineer writes a handoff report for the incoming engineer

This process is entirely manual, repetitive, and depends heavily on individual engineer experience. Alert volumes can spike during incidents, creating cognitive overload and SLA breach risk.

---

## III. Problem Statement

The NOC faces several recurring operational challenges:
- **Alert fatigue:** High alert volumes cause engineers to miss or delay critical incidents
- **Inconsistent triage:** Severity classification and team routing vary between engineers
- **Duplicate noise:** The same underlying fault triggers multiple alerts, wasting engineer time
- **SLA pressure:** Critical incidents have 15-minute response windows; manual triage consumes 5–10 minutes
- **Knowledge gap:** Newer engineers lack runbook knowledge for complex faults
- **Shift handoff loss:** Incident context is lost between shifts without structured documentation

**Thesis Statement:** An AI-powered triage agent with Human-in-the-Loop oversight can significantly reduce mean time to triage, improve consistency, and provide decision support that augments rather than replaces NOC engineers.

---

## IV. Objectives

1. Build a multi-agent AI pipeline that automatically triages incoming NOC alerts
2. Implement deduplication logic to suppress repeated alerts from the same root fault
3. Implement a Supervisor Agent that independently re-classifies alert categories to catch mislabeling
4. Build a Runbook Agent that retrieves the relevant standard operating procedure for each alert
5. Implement cross-ticket root cause correlation to detect cascading failures
6. Integrate with an ITSM system (GLPI) to automatically create and assign tickets on engineer approval
7. Build a Human-in-the-Loop interface where engineers review AI output and make the final decision
8. Implement SLA tracking and automatic escalation when HITL review exceeds thresholds
9. Build an analytics dashboard for shift supervisors to track NOC performance
10. Build a NOC AI Assistant chatbot for engineers to query the alert queue conversationally

---

## V. Courses Linked to This Project

This project applies knowledge from multiple courses in the AI program:

| Course | Application in This Project |
|--------|----------------------------|
| Natural Language Processing | LLM-based alert classification, root cause analysis, and runbook retrieval |
| Machine Learning | Confidence scoring, similarity-based deduplication, correlation detection |
| Software Engineering | Modular system design, API design (FastAPI), Git version control |
| Database Systems | SQLite persistence (LangGraph SqliteSaver), JSON audit logging |
| Computer Networks | Telecom domain knowledge — BGP, OSPF, DHCP, MPLS, STP, VLANs |
| [Course Name — AI Agents / Intelligent Systems] | LangGraph state machines, multi-agent orchestration, HITL patterns |

---

## VI. New Skills Learned

The following skills were acquired or significantly developed during this internship:

1. **LangGraph** — Building graph-based AI agent state machines with interrupt/resume for human approval
2. **Groq API** — Low-latency LLM inference; handled Python 3.14 / Pydantic V1 incompatibility by building a raw SDK shim
3. **FastAPI** — RESTful API design, Server-Sent Events (SSE) for streaming, async endpoints
4. **React + Vite** — Modern frontend development with React Router, Recharts, and live polling
5. **GLPI REST API** — ITSM ticket creation, SLA assignment, group management, email notifications
6. **Docker** — Running containerized services (GLPI + MariaDB) and managing service dependencies
7. **LLM prompt engineering** — Multi-turn context, scope hardening against prompt injection, structured JSON output
8. **Retrieval-Augmented Generation (RAG)** — LLM-based document retrieval without vector databases or GPU

---

## VII. System Architecture

The system has three main interfaces that all share one AI backend:

```
┌─────────────────────────────────────────────────────────────┐
│                        Data Sources                         │
│   Mock CSV (80 alerts) / GLPI polling / Meraki webhooks     │
└────────────────────────────┬────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │  Streamlit   │   │    React     │   │     GLPI     │
  │  Port 8501   │   │  Port 5173   │   │   Port 80    │
  │  (Original)  │   │  (New UI)    │   │  (ITSM)      │
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
         │                  │                  │
         │            ┌─────▼──────┐   ┌───────▼────────┐
         │            │  FastAPI   │   │ glpi_agent.py  │
         │            │  Port 8001 │   │  (polls 15s)   │
         │            └─────┬──────┘   └───────┬────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
          ┌─────────────────────────────────┐
          │       src/agent_graph.py        │
          │   LangGraph Multi-Agent Brain   │
          │                                 │
          │  Triage → Dedup → Supervisor    │
          │  → Specialist → Runbook         │
          │  → Correlation → HITL Pause     │
          └─────────────────────────────────┘
                            │
                            ▼
          ┌─────────────────────────────────┐
          │   Groq API — LLaMA 3.3 70B     │
          └─────────────────────────────────┘
```

---

## VIII. The AI Pipeline (agent_graph.py)

The heart of the system is a LangGraph state machine with 9 nodes:

```
START
  │
  ▼
[1] triage_node
    Logs the incoming ticket and initialises the agent state.
  │
  ▼
[2] deduplication_node
    Checks SQLite history + LLM to determine if this alert is a repeat.
  │
  ├── (duplicate) → [3] drop_node → HITL PAUSE (engineer approves drop or keeps)
  │
  └── (unique) → [4] supervisor_node
                    LLM independently re-classifies the alert category.
                    Stores reason in supervisor_reason.
                    (Example: an alert mislabeled "Application" was overridden
                    to "Network" at 92% confidence.)
                  │
                  ▼
              Route to specialist:
              ├── [5a] network_ops_node   (BGP, OSPF, VLAN, DHCP, DNS)
              ├── [5b] security_ops_node  (DDoS, malware, brute force, certs)
              ├── [5c] hardware_ops_node  (PSU, fans, disk, NIC, temperature)
              ├── [5d] cloud_ops_node     (AWS, Kubernetes, VM, auto-scaling)
              └── [5e] application_ops_node (ERP, SAP, DB, API, SMTP)
                  │
                  ▼
              [6] runbook_node
                  LLM retrieves most relevant runbook from 13 JSON SOPs.
                  Returns: steps, resolution, escalation path, confidence %.
                  (Threshold: 50% — below this, no runbook shown.)
                  │
                  ▼
              [7] correlation_node
                  Checks last 10 tickets in memory for shared root cause.
                  Sets is_correlated + correlated_with fields.
                  │
                  ▼
              [8] remedy_node ← HITL PAUSE (engineer reviews, approves/rejects)
                  On approval: creates GLPI ticket + sends email notification
                  GLPI body includes matched runbook + supervisor reason
                  │
                  ▼
              END
```

**Interrupt Points:** The graph pauses at `remedy` and `drop` nodes. No action is taken until the engineer explicitly approves. This is the core HITL guarantee.

### AgentState Fields

| Field | Type | Description |
|-------|------|-------------|
| ticket_id | str | Unique alert identifier |
| category | str | Network / Security / Hardware / Cloud / Application |
| description | str | Alert message |
| logs | str | Raw syslog or event logs |
| analysis | str | JSON string — full LLM analysis output |
| is_duplicate | bool | True if deduplication node flagged this |
| duplicate_reason | str | Explanation of why it's a duplicate |
| is_correlated | bool | True if correlated with a recent ticket |
| correlated_with | str | Ticket ID of the correlated ticket |
| confidence_score | int | 0–100 from the specialist LLM analysis |
| severity | str | Critical / High / Medium / Low |
| recommendation | str | Step-by-step remediation from LLM |
| glpi_ticket_id | str | GLPI ticket number created on approval |
| supervisor_reason | str | Why the Supervisor node chose this category |
| runbook_match | str | Formatted runbook text, empty if no match |
| skip_email | bool | True = engineer chose to skip email notification |

---

## IX. Key Features

### 1. Human-in-the-Loop (HITL) Design
Every ticket must be approved by an engineer before any ticket is created or email sent. The AI assists — it never acts autonomously. This was a deliberate design decision to match how Emircom's NOC actually operates.

### 2. Multi-Agent Supervisor
A dedicated Supervisor LLM node independently re-classifies every alert before routing. This catches mislabeled alerts (e.g., a network failure submitted as "Application" gets corrected to "Network"). Verified with a live test: Network alert submitted as Application → Supervisor overrode to Network at 92% confidence.

### 3. RAG-Based Runbook Agent
13 realistic standard operating procedures (SOPs) were written in JSON format covering all 5 alert categories. The Runbook Agent uses a single LLM prompt (no vector database, no GPU required) to identify the best-matching runbook. Engineers see the step-by-step diagnosis and resolution procedure in the HITL review panel.

Verified match rates: OSPF loss → 98%, UPS failure → 95%, Database timeout → 95%, PSU failure → 92%.

### 4. Deduplication Engine
Uses SQLite persistence + LLM similarity check to detect duplicate alerts. Cross-session persistence means a duplicate is caught even after the app restarts. Engineers can override the duplicate judgment and keep the ticket.

### 5. Root Cause Correlation
Checks the current alert against the last 10 processed tickets in agent memory. If the LLM identifies a shared root cause, an orange warning banner appears in the HITL panel: "This ticket may share root cause with INC-XXXX."

### 6. SLA Tracking and Escalation Agent
- SLA thresholds: Critical=15min, High=1hr, Medium=4hr, Low=24hr
- Live countdown timer displayed during HITL review
- If a Critical ticket sits unacknowledged for >5 minutes (High >15 min), a pulsing red banner appears and an escalation email is automatically sent to the Shift Lead
- One email per ticket, never repeated

### 7. GLPI ITSM Integration
GLPI (open-source ITSM) runs in Docker as a substitute for Emircom's Remedy system. On engineer approval:
- Ticket created with AI-generated description (includes runbook + supervisor reason)
- Priority set from severity (Critical=6, High=4, Medium=3, Low=2)
- NOC team group assigned (5 groups matching the 5 categories)
- SLA rule applied automatically
- Email notification sent via Gmail SMTP

### 8. NOC AI Chatbot
A conversational assistant for engineers, embedded in the dashboard. Engineers can ask questions like "What's the current Critical count?" or "Summarize the last 5 tickets." The chatbot:
- Streams responses token-by-token for responsiveness
- Has the full pending alert queue in its context every turn
- Has a "Paste Logs" button to analyze raw syslog on the fly
- Resists prompt injection, persona-change attacks, and off-topic questions (scope-hardened system prompt, two rounds of adversarial testing)

### 9. Dual Dashboard (Streamlit + React)
Two complete dashboard implementations exist:

**Streamlit** (port 8501) — Full-featured original dashboard:
- Tab 1: Operations Center — HITL panel with 4 sub-tabs (Summary, Raw Logs, Runbook, Email Template), SLA timer, confidence score, severity filters, back-to-queue button
- Tab 2: Analytics — 6 KPI cards, 6 Plotly charts, filterable audit log, Word/Excel shift report generation
- Tab 3: NOC AI Assistant — streaming chatbot

**React** (port 5173 + FastAPI on 8001) — Modern production-ready UI:
- Dashboard page: stat cards, shift briefing banner (AI-generated), alert queue, GLPI notification panel
- Operations page: 2-step HITL wizard, escalation/duplicate/correlation banners, 4-tab review panel
- Analytics page: 6 KPI cards, 6 Recharts charts, filterable audit log, PIR downloads
- Chatbot page: SSE streaming, suggestion chips, Paste Logs
- Reports page: shift handoff form, Excel export, PIR list

### 10. Cisco DevNet + Meraki Integration
- Cisco DNA Center connector pulls live device health alerts from the DevNet sandbox
- Meraki webhook receiver (FastAPI, port 8003) accepts real-time Meraki dashboard alerts
- These replace the mock CSV as alternate data sources

---

## X. Data Layer

### Mock Dataset
80 telecom-grade NOC incidents (INC-3001 – INC-3080) covering all 5 categories with realistic syslog content:

| Category | Alert Types |
|----------|-------------|
| Network | BGP failures, OSPF adjacency drops, DHCP exhaustion, interface flaps, bandwidth saturation, LACP, STP changes, WAN outages |
| Security | Malware, DDoS (4.2 Gbps), brute force, SSL expiry, ransomware indicators, unauthorized access |
| Hardware | PSU failures, fan failures, disk failures, NIC errors, temperature alerts, ECC memory |
| Cloud | EC2 failures, S3 issues, Kubernetes pod crashes, CDN outages, auto-scaling failures |
| Application | ERP/SAP outages, API gateway errors, DB replication lag, SMTP failures, memory leaks, billing errors |

Intentional near-duplicates are included to test the deduplication engine.

### Audit Log
Every processed ticket is written to `data/processed_tickets.json` with: Ticket_ID, Category, Severity, Status, GLPI ticket number, SLA_Breached flag, Confidence_Score, Response_Time_Secs, Correlated_With.

### LangGraph Persistence
Agent state stored in SQLite (`data/noc_memory.db`) per ticket thread. Enables cross-session deduplication and correlation.

---

## XI. Technical Stack

| Layer | Technology |
|-------|-----------|
| AI Orchestration | LangGraph (graph-based state machine) |
| LLM | LLaMA 3.3 70B via Groq API (temperature 0.1) |
| LLM Client | Raw Groq SDK (custom `_LazyLLM` shim — avoids Python 3.14 deadlock) |
| Backend | Python 3.14, FastAPI, Uvicorn |
| Streamlit UI | Streamlit 1.x (modular: 6 files) |
| React UI | React 18, Vite, React Router v7, Recharts, Axios |
| ITSM | GLPI (Docker) + MariaDB (Docker) |
| Agent Memory | SQLite via LangGraph SqliteSaver |
| Email | Gmail SMTP, App Password, STARTTLS |
| Network Integration | Cisco DNA Center REST API, Meraki Webhook (FastAPI) |
| Report Generation | python-docx (Word), openpyxl (Excel) |
| Version Control | Git, GitHub (YznCodeX/Emircom_NOC_Agent) |

---

## XII. Challenges and How They Were Solved

| Challenge | Solution |
|-----------|----------|
| **Python 3.14 incompatibility** — `langchain_groq` deadlocked on startup due to Pydantic V1 / Python 3.14 conflict | Built a `_LazyLLM` shim that wraps the raw `groq.Groq` client, exposing the same `.invoke()` interface. All agents use this shim. `langchain_groq` is never imported. |
| **Groq free-tier rate limits** (12,000 TPM) | Designed the pipeline to process one ticket at a time; added user-facing rate limit messages instead of silent crashes; GLPI agent posts "retry next cycle" message instead of raw Python errors |
| **No access to real Emircom data** | Built 80 realistic telecom-grade mock alerts with authentic syslog content; wrote 13 realistic JSON runbooks; used Cisco DevNet sandbox for real device data |
| **No GPU / No vector database** | Replaced the original HuggingFace BGE-M3 embedding approach with a single LLM prompt that reads a runbook index and selects the best match directly — no GPU, no embedding model, no infrastructure cost |
| **Wrong ticket data appearing in email panel** | Snapshot pattern: ticket data is captured into `email_snap_*` session state variables at the moment the engineer clicks Approve, not read from live state. This prevents stale or wrong-ticket data from appearing after state changes. |
| **SQLite thread-safety in Streamlit** | SqliteSaver initialized with `check_same_thread=False` because Streamlit reruns can use different threads |
| **No Remedy API access** | GLPI (open-source ITSM in Docker) was configured to mirror Remedy functionality: 5 NOC groups, 4 SLA rules, 5 ITIL categories, priority mapping, branded email template |

---

## XIII. Limitations and Honest Assessment

| Limitation | Impact |
|-----------|--------|
| Mock data only | System has not processed real Emircom alerts; awaiting supervisor approval for production data access |
| Fake runbooks | 13 JSON SOPs are realistic but not actual Emircom procedures; real SOPs can be dropped into `data/emircom_runbooks/` with no code changes |
| No Remedy integration | GLPI is functionally equivalent for a prototype but is not the system Emircom actually uses |
| Groq free tier | Rate limits (~12,000 TPM) cause delays when processing multiple tickets rapidly; production would require a paid tier or a locally hosted model |
| Single-user, no authentication | The prototype has no login system; anyone with the URL can access the dashboard |
| LLM quality depends on log detail | Vague or minimal log content produces lower confidence scores; real monitoring system logs would significantly improve analysis quality |

---

## XIV. Results and Measured Outcomes

| Metric | Value |
|--------|-------|
| Tickets in mock dataset | 80 |
| Alert categories covered | 5 (Network, Security, Hardware, Cloud, Application) |
| Runbooks in RAG library | 13 |
| Runbook match rate (tested categories) | OSPF: 98%, UPS: 95%, DB timeout: 95%, PSU: 92% |
| Supervisor override accuracy | Verified: mislabeled Network→Application corrected to Network at 92% confidence |
| Escalation detection | Banner fires within 10 seconds of threshold breach (tested on Critical ticket INC-3812) |
| Deduplication | Cross-session persistence verified; duplicate correctly detected after app restart |
| GLPI integration | Ticket creation, SLA assignment, team routing, email notification — all tested end-to-end |
| Total features implemented | 30+ (see Feature Status table in PROJECT_REPORT.md) |

---

## XV. Conclusion

This project demonstrates that an AI-powered triage agent can meaningfully assist NOC engineers by automating the most time-consuming and error-prone parts of incident triage. The Human-in-the-Loop design ensures engineers remain in control, which is critical in a 24/7 operational environment where a wrong action can cause service disruption.

The system is production-ready in architecture — it uses industry-standard tools (LangGraph, FastAPI, React, Docker, GLPI REST API) and has been designed to scale. The primary remaining step is supervisor approval to connect to real Emircom alert feeds and replace the mock data with live incidents.

The internship provided hands-on experience with AI agent design, full-stack development, ITSM integration, DevOps (Docker), and telecom domain knowledge — competencies directly applicable to AI engineering roles in enterprise IT operations.

---

## XVI. Suggestions for Improvement

1. **Real data integration** — The single highest-impact next step is connecting to Emircom's actual monitoring system. Mock data validates the pipeline; real data will reveal edge cases and allow measurement of actual MTTR reduction.
2. **Upgrade to paid Groq tier or self-hosted model** — Remove the rate-limit constraint for production use.
3. **Authentication and RBAC** — Add login with engineer roles (Tier-1, Tier-2, Shift Lead, Manager).
4. **Real Emircom runbooks** — The retrieval engine is fully built and ready; only the JSON files need to be replaced.
5. **Teams integration** — Read maintenance notifications from Teams channels to auto-suppress planned outage alerts.
6. **Historical trend analysis** — After 30+ days of real data, identify devices with recurring failures for proactive maintenance.

---

*Project Repository: github.com/YznCodeX/Emircom_NOC_Agent*  
*Contact: [Your student email]*
