"""
Meraki Webhook Receiver
-----------------------
FastAPI server that receives real-time alerts from Cisco Meraki Dashboard.
Parses the payload, converts it to the NOC agent format, and runs it through
the agent graph → GLPI ticket created automatically.

Run:
    uvicorn meraki.webhook_receiver:app --host 0.0.0.0 --port 8001 --reload
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import uuid
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from meraki.meraki_parser import parse_meraki_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Meraki] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Emircom NOC — Meraki Webhook Receiver")

# Optional: shared secret validation (set in Meraki Dashboard → Webhooks)
MERAKI_SECRET = os.getenv("MERAKI_WEBHOOK_SECRET", "")


@app.get("/")
def health():
    return {"status": "ok", "service": "Emircom NOC Meraki Receiver"}


@app.get("/webhook/meraki")
def meraki_ping():
    """Meraki sends a GET first to verify the endpoint is alive."""
    return {"status": "ok"}


@app.post("/webhook/meraki")
async def receive_meraki_alert(request: Request):
    """
    Main webhook endpoint — Meraki POSTs here when an alert fires.
    Validates the secret, parses the payload, and runs the NOC agent.
    """
    body = await request.body()

    # Validate shared secret if configured
    if MERAKI_SECRET:
        secret_header = request.headers.get("X-Cisco-Meraki-Signature-v1", "")
        if secret_header != MERAKI_SECRET:
            raise HTTPException(status_code=401, detail="Invalid shared secret")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    log.info(f"Received alert type: {payload.get('alertType', 'unknown')}")

    # Parse into NOC agent format
    alert = parse_meraki_alert(payload)
    if alert is None:
        log.info("Alert filtered out (not actionable)")
        return JSONResponse({"status": "ignored", "reason": "not actionable"})

    log.info(f"Processing alert: {alert['Ticket_ID']} — {alert['Alert_Message']}")

    # Run through the NOC agent graph
    try:
        from src.agent_graph import app as agent_app

        state = {
            "ticket_id":   alert["Ticket_ID"],
            "category":    alert["Category"],
            "description": alert["Alert_Message"],
            "logs":        alert["Raw_Logs"],
            "analysis":    "",
            "is_duplicate":    False,
            "duplicate_reason": "",
            "is_correlated":   False,
            "correlated_with": "",
            "confidence_score": 0,
            "severity":    alert.get("Severity", "Medium"),
            "recommendation": "",
            "glpi_ticket_id": "",
        }
        config = {"configurable": {"thread_id": alert["Ticket_ID"]}}

        # Step 1: Run until interrupt (before remedy)
        agent_app.invoke(state, config=config)

        # Step 2: Resume past the interrupt — auto-approve for webhook alerts
        result = agent_app.invoke(None, config=config)

        glpi_id = result.get("glpi_ticket_id", "")
        log.info(f"GLPI ticket created: #{glpi_id}")
        return JSONResponse({
            "status": "processed",
            "ticket_id": alert["Ticket_ID"],
            "glpi_ticket_id": glpi_id,
        })
    except Exception as e:
        log.error(f"Agent error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("meraki.webhook_receiver:app", host="0.0.0.0", port=8001, reload=True)
