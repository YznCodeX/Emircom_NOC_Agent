from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import pandas as pd
import os
import io
import requests as http_requests

from src.agent_graph import app as agent_app, _glpi_create_ticket

GLPI_BASE  = "http://localhost/api.php/v1"
APP_TOKEN  = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN = "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"

def glpi_session():
    r = http_requests.get(f"{GLPI_BASE}/initSession", headers={
        "App-Token": APP_TOKEN,
        "Authorization": f"user_token {USER_TOKEN}"
    }, timeout=10)
    return r.json().get("session_token")

def glpi_headers(token):
    return {"App-Token": APP_TOKEN, "Session-Token": token, "Content-Type": "application/json"}

app = FastAPI(title="Emircom NOC Agent API")

# Allow React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = "data/mock_tickets.csv"
PROCESSED_PATH = "data/processed_tickets.json"


def load_processed():
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, "r") as f:
            return json.load(f)
    return []


def save_processed(tickets):
    with open(PROCESSED_PATH, "w") as f:
        json.dump(tickets, f, indent=2)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/tickets")
def get_tickets():
    """Return all unprocessed tickets from the CSV."""
    df = pd.read_csv(DATA_PATH)
    processed_ids = {t["Ticket_ID"] for t in load_processed()}
    pending = df[~df["Ticket_ID"].isin(processed_ids)]
    return pending.to_dict(orient="records")


@app.get("/tickets/processed")
def get_processed_tickets():
    """Return all processed tickets."""
    return load_processed()


class AnalyzeRequest(BaseModel):
    ticket_id: str
    category: str
    description: str
    logs: str


@app.post("/tickets/analyze")
def analyze_ticket(req: AnalyzeRequest):
    """Run the AI agent on a ticket and return the analysis."""
    config = {"configurable": {"thread_id": req.ticket_id}}
    inputs = {
        "ticket_id": req.ticket_id,
        "category": req.category,
        "description": req.description,
        "logs": req.logs,
    }
    agent_app.invoke(inputs, config=config)
    state = agent_app.get_state(config)
    analysis_raw = state.values.get("analysis", "{}")
    try:
        analysis = json.loads(analysis_raw.replace("```json", "").replace("```", "").strip())
    except Exception:
        analysis = {"raw": analysis_raw}

    return {
        "ticket_id": req.ticket_id,
        "analysis": analysis,
        "is_duplicate": state.values.get("is_duplicate", False),
        "is_correlated": state.values.get("is_correlated", False),
        "correlated_with": state.values.get("correlated_with", ""),
        "confidence_score": state.values.get("confidence_score", 0),
        "next_node": list(state.next) if state.next else [],
    }


class ApproveRequest(BaseModel):
    ticket_id: str
    category: str
    severity: str
    action: str  # "approve" or "reject"


@app.post("/tickets/approve")
def approve_ticket(req: ApproveRequest):
    """Approve or reject a ticket. If approved, creates a GLPI ticket."""
    glpi_id = None
    if req.action == "approve":
        config = {"configurable": {"thread_id": req.ticket_id}}
        agent_app.invoke(None, config=config)
        glpi_id = _glpi_create_ticket(
            f"[NOC] {req.category} - {req.ticket_id}",
            f"Severity: {req.severity}\nApproved via NOC Agent.",
            req.severity
        )

    processed = load_processed()
    processed.append({
        "Ticket_ID": req.ticket_id,
        "Category": req.category,
        "Severity": req.severity,
        "Status": "Approved" if req.action == "approve" else "Rejected",
        "GLPI_Ticket": glpi_id,
        "SLA_Breached": False,
        "Confidence_Score": "",
    })
    save_processed(processed)

    return {"status": "ok", "glpi_ticket": glpi_id}


@app.get("/stats")
def get_stats():
    """Return summary stats for the dashboard."""
    processed = load_processed()
    return {
        "total": len(processed),
        "approved": sum(1 for t in processed if t["Status"] == "Approved"),
        "rejected": sum(1 for t in processed if t["Status"] == "Rejected"),
        "critical": sum(1 for t in processed if t.get("Severity") == "Critical"),
        "high": sum(1 for t in processed if t.get("Severity") == "High"),
    }


@app.get("/glpi/pending-review")
def get_glpi_pending_review():
    """Return GLPI tickets that the agent has analyzed (status=Pending) awaiting engineer review."""
    try:
        session = glpi_session()
        headers = glpi_headers(session)

        # Get tickets with status = Pending (4)
        r = http_requests.get(f"{GLPI_BASE}/Ticket", headers=headers, params={
            "range": "0-50",
            "sort": "date_mod",
            "order": "DESC",
        }, timeout=10)
        all_tickets = r.json() if isinstance(r.json(), list) else []

        # Filter pending (status=4) tickets
        pending = [t for t in all_tickets if t.get("status") == 4]

        result = []
        for t in pending:
            # Get followups (comments) for this ticket
            fu = http_requests.get(f"{GLPI_BASE}/Ticket/{t['id']}/ITILFollowup", headers=headers, timeout=10)
            followups = fu.json() if isinstance(fu.json(), list) else []
            ai_comment = ""
            assigned_team = ""
            for f in followups:
                content = f.get("content", "")
                if "AI NOC Agent" in content:
                    ai_comment = content
                    # Extract assigned team from comment
                    import re
                    m = re.search(r"Assigned Team:\s*(.+)", content)
                    if m:
                        assigned_team = m.group(1).strip()
                    break

            # Also fetch group assignment from Group_Ticket
            if not assigned_team:
                grp = http_requests.get(
                    f"{GLPI_BASE}/Ticket/{t['id']}/Group_Ticket",
                    headers=headers, timeout=10
                )
                grp_data = grp.json() if isinstance(grp.json(), list) else []
                for g in grp_data:
                    if g.get("type") == 2:  # assigned group
                        assigned_team = g.get("groups_name", "")
                        break

            result.append({
                "glpi_id": t["id"],
                "title": t.get("name", "Unknown"),
                "priority": t.get("priority", 3),
                "status": t.get("status"),
                "ai_comment": ai_comment,
                "assigned_team": assigned_team,
            })

        http_requests.get(f"{GLPI_BASE}/killSession", headers=headers, timeout=5)
        return result

    except Exception as e:
        return []


@app.get("/handoff/export")
def export_handoff_excel():
    """Export processed tickets as a multi-sheet Excel file for handoff report."""
    processed = load_processed()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Audit Log
        df = pd.DataFrame(processed) if processed else pd.DataFrame(
            columns=['Ticket_ID', 'Category', 'Severity', 'Status', 'GLPI_Ticket', 'SLA_Breached', 'Confidence_Score']
        )
        df.to_excel(writer, sheet_name='Audit Log', index=False)

        # Sheet 2: Summary
        pd.DataFrame({
            'Metric': ['Total Processed', 'Approved', 'Rejected', 'Critical', 'High', 'Medium', 'Low'],
            'Count': [
                len(processed),
                sum(1 for t in processed if t.get('Status') == 'Approved'),
                sum(1 for t in processed if t.get('Status') == 'Rejected'),
                sum(1 for t in processed if t.get('Severity') == 'Critical'),
                sum(1 for t in processed if t.get('Severity') == 'High'),
                sum(1 for t in processed if t.get('Severity') == 'Medium'),
                sum(1 for t in processed if t.get('Severity') == 'Low'),
            ]
        }).to_excel(writer, sheet_name='Summary', index=False)

        # Sheet 3: By Category
        categories = {}
        for t in processed:
            cat = t.get('Category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        if categories:
            pd.DataFrame([{'Category': k, 'Count': v} for k, v in categories.items()]).to_excel(
                writer, sheet_name='By Category', index=False
            )

    output.seek(0)
    filename = f"noc_handoff_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


class GLPIActionRequest(BaseModel):
    glpi_id: int
    action: str  # "approve" or "reject"


@app.post("/glpi/action")
def glpi_action(req: GLPIActionRequest):
    """Approve (Solved=5) or Reject (Closed=6) a GLPI ticket."""
    try:
        session = glpi_session()
        headers = glpi_headers(session)

        new_status = 5 if req.action == "approve" else 6  # 5=Solved, 6=Closed
        http_requests.put(f"{GLPI_BASE}/Ticket/{req.glpi_id}", headers=headers, json={
            "input": {"status": new_status}
        }, timeout=10)

        http_requests.get(f"{GLPI_BASE}/killSession", headers=headers, timeout=5)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
