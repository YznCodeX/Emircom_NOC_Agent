# Emircom NOC Agent — CLAUDE.md
> Read this first. It replaces reading the large source files at session start.

## Project in One Line
AI-powered NOC triage agent: alerts come in → multi-agent pipeline → engineer reviews (HITL) → GLPI ticket + email out.

## Owner
Yazan — final semester AI student, unpaid trainee at Emircom. Supervisor not yet assigned.
Graded: presentation 40% / report 30% / supervisor 30%.

---

## Repo Layout (only files that matter)
```
src/
  agent_graph.py        # THE brain — LangGraph pipeline, all nodes, AgentState
  email_sender.py       # Gmail SMTP email sender
  escalation_agent.py   # fires pulsing banner + email when HITL overdue
  rag_core.py           # Runbook Agent — LLM-based retrieval (no vector DB)

streamlit/
  app.py                # Main UI — 1700+ lines, Streamlit dashboard

glpi/
  glpi_agent.py         # Background worker — polls GLPI every 15s
  push_to_glpi.py       # One-shot script to push test tickets

cisco/
  devnet_connector.py   # Cisco DNA Center connector (DevNet sandbox)

meraki/
  webhook_receiver.py   # FastAPI on port 8003, receives Meraki alerts
  meraki_parser.py      # Parses Meraki webhook payloads

data/
  mock_tickets.csv      # 50 telecom-grade mock alerts
  emircom_runbooks/     # 13 runbook JSON files for RAG
  processed_tickets.json  # audit log — appended by _save_and_advance()
  session_state.json    # persists ticket_index across restarts

frontend/               # React + Vite dashboard (FastAPI backend on 8001)
api/
  main.py               # FastAPI backend for React frontend
```

---

## The Pipeline (agent_graph.py)
```
Input {ticket_id, category, description, logs}
  → triage_node
  → deduplication_node  ──(duplicate)──→ [DROP interrupt] → END
  → supervisor_node     # LLM re-classifies category, sets supervisor_reason
  → route_after_supervisor()
  → [network/security/hardware/cloud/application]_ops_node
  → runbook_node        # RAG: matches best runbook from 13 JSON files
  → correlation_node    # checks cross-ticket root cause
  → [HITL interrupt at remedy node — waits for engineer]
  → remedy_node         # creates GLPI ticket + sends email
  → END
```

**interrupt_before = ["remedy", "drop"]** — graph pauses here for human review.

---

## AgentState Fields
```python
ticket_id, category, description, logs   # inputs
analysis          # JSON string from specialist node
is_duplicate, duplicate_reason
is_correlated, correlated_with
confidence_score  # 0-100 int
severity          # "Critical"/"High"/"Medium"/"Low" — from LLM analysis
recommendation
glpi_ticket_id
supervisor_reason # one-sentence why supervisor picked this specialist
runbook_match     # formatted runbook text, "" if no match
skip_email        # bool — True = engineer chose Skip in email panel
```

---

## ⚠️ CRITICAL — Never Break These Rules

### 1. NEVER use `langchain_groq`
It hangs on Python 3.14 (pydantic v1 incompatibility). Use the `_LazyLLM` shim in `agent_graph.py`:
```python
from src.agent_graph import llm
response = llm.invoke("prompt string")   # returns _Msg with .content
```

### 2. LLM response parsing pattern
```python
raw = response.content.replace("```json","").replace("```","").strip()
parsed = json.loads(raw)
```

### 3. SQLite checkpointer thread_id = ticket_id
Each ticket gets its own LangGraph thread. `app.get_state({"configurable": {"thread_id": "INC-XXXX"}})` to inspect.

### 4. Streamlit is single-threaded
No background threads. Escalation check piggybacks on the 1-second SLA rerun loop.

---

## Groq Free Tier Limits
- Model: `llama-3.3-70b-versatile`
- **12,000 TPM (tokens per minute)** — hits after ~2-3 tickets processed rapidly
- Rate limit error: `429 RateLimitError` from `groq._base_client`
- Fix: wait ~60 seconds, the window resets

---

## Streamlit App Key Session State
```python
thread_id            # current ticket's LangGraph thread
waiting_for_user     # True = HITL panel is showing
email_confirm_pending  # True = showing email notification panel
email_snap_tid/cat/sev/node/team  # snapshots of ticket data at approve-click
sla_start_time       # time.time() when ticket entered HITL
escalation_sent      # bool — escalation email fired for this ticket
ticket_index         # current position in mock_tickets.csv
processed_tickets    # list of dicts — in-memory audit log
```

### HITL Flow (app.py)
1. Engineer clicks ▶ → `analyze_current_ticket()` → `app.invoke()` → pauses at remedy
2. HITL panel renders (Summary / Raw Logs / Runbook / Email Template tabs)
3. Engineer clicks **Approve & Escalate** → snapshots ticket data → `email_confirm_pending = True`
4. Email notification panel renders (dark-themed card, severity accent border)
5. Engineer clicks **Send Notification** or **Skip** → `app.invoke(None, config)` → remedy_node runs
6. `_save_and_advance()` → appends to processed_tickets.json, resets state
7. `analyze_current_ticket()` → loads next ticket → `st.rerun()`

**Duplicate DROP tickets bypass the email panel entirely.**

---

## Email Notification Panel (step 2 of approval)
- Dark-themed card: `rgba(255,255,255,0.05)` background, severity-colored left border
- Shows: To / Subject / Team / Affected Node
- Buttons: `✉️ Send Notification` (primary) / `Skip` (secondary)
- Data comes from **snapshots** (`email_snap_*`) NOT live session state — prevents wrong-ticket bug
- `skip_email=True` injected into LangGraph state via `app.update_state()` before resume

---

## GLPI Integration
- Docker containers: `glpi` (diouxx/glpi) + `mariadb` (10.7)
- URL: http://localhost | Login: glpi / glpi
- 5 NOC groups, 4 SLA rules, 5 ITIL categories (auto-assigned)
- Background worker: `glpi/glpi_agent.py` — polls every 15s, posts AI analysis as comment
- Email: Gmail SMTP (`emircom.noc.agent@gmail.com`), App Password in `.env`
- GLPI ticket enrichment: includes matched runbook + supervisor routing reason in body

### Reset GLPI admin password (if locked out):
```bash
docker exec glpi php -r "
\$hash = password_hash('glpi', PASSWORD_BCRYPT);
\$pdo = new PDO('mysql:host=mariadb;dbname=glpidb', 'glpi', 'glpi');
\$pdo->prepare('UPDATE glpi_users SET password=? WHERE name=?')->execute([\$hash,'glpi']);
echo 'Done: '.\$hash;
"
# If user is missing, also run:
docker exec glpi php -r "
\$pdo = new PDO('mysql:host=mariadb;dbname=glpidb','glpi','glpi');
\$uid = \$pdo->query('SELECT id FROM glpi_users WHERE name=chr(103).chr(108).chr(112).chr(105)')->fetchColumn();
\$pdo->exec('DELETE FROM glpi_profiles_users WHERE users_id='.\$uid);
\$pdo->exec('INSERT INTO glpi_profiles_users(users_id,profiles_id,entities_id,is_recursive,is_dynamic) VALUES('.\$uid.',4,0,1,0)');
echo 'Profile assigned';
"
```

---

## Services & Ports
| Service | Port | Start Command |
|---------|------|---------------|
| Streamlit | 8501 | `venv\Scripts\streamlit run streamlit/app.py` |
| FastAPI (React backend) | 8001 | `venv\Scripts\uvicorn api.main:app --port 8001` |
| React frontend | 5173 | `cd frontend && npm run dev` |
| GLPI agent | — | `venv\Scripts\python glpi/glpi_agent.py` |
| Meraki webhook | 8003 | `venv\Scripts\uvicorn meraki.webhook_receiver:app --port 8003` |
| GLPI | 80 | Docker (starts with `docker start glpi mariadb`) |
| One-shot start | all | `.\start_noc.ps1` |

---

## Runbook Agent (RAG)
- 13 runbooks in `data/emircom_runbooks/*.json`
- No vector DB — single LLM prompt reads runbook index and picks best match
- Confidence threshold: 50% (below = "No match")
- `runbook_node` in `agent_graph.py`, called after specialist node
- Results shown in HITL panel under 📖 Runbook tab

---

## Escalation Agent
- File: `src/escalation_agent.py`
- Thresholds: Critical > 5 min, High > 15 min unacknowledged at HITL
- Runs inside SLA rerun loop (no background threads)
- Fires: pulsing red banner in UI + email to `SHIFT_LEAD_EMAIL` env var
- One email per ticket (`escalation_sent` session state flag)

---

## NOC Chatbot
- In `streamlit/app.py` under "🤖 NOC Chatbot" tab
- Streaming output via `llm.stream(messages)`
- Knows live pending queue
- Scope-hardened: rejects off-topic and prompt injection attempts
- 📋 Paste Logs button for raw syslog input

---

## What's Pending (waiting for supervisor)
- Real Emircom runbooks → drop JSON files in `data/emircom_runbooks/`
- Real Remedy API access (GLPI is the substitute)
- Microsoft 365 API (Teams/email integration)
- Real alert feed (currently mock CSV or DevNet sandbox)

---

## GitHub
Repo: `YznCodeX/Emircom_NOC_Agent` (main branch)
All commits use: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

---

## Quick Reference — Common Fixes
| Problem | Fix |
|---------|-----|
| Groq 429 rate limit | Wait 60s, try again |
| GLPI won't start | `docker start glpi mariadb` |
| `langchain_groq` import hang | Already fixed — use `_LazyLLM` shim, never revert |
| Email not sending | Check `.env` for `GMAIL_USER`, `GMAIL_APP_PASSWORD` |
| Streamlit crash on int64 | `int(value)` before storing to session state |
| Wrong ticket in email panel | Uses `email_snap_*` snapshots — check snapshot logic |
| Dedup not working | SQLite file at `data/dedup.db` — delete to reset |
