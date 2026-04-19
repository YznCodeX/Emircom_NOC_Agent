"""
persistence.py — Disk I/O helpers for tickets and queue state
=============================================================

What this file is responsible for
----------------------------------
Reading and writing the two JSON files that keep the app alive across
Streamlit restarts:

  data/processed_tickets.json
      An append-only audit log of every ticket the engineer has reviewed
      this shift (Approved / Rejected / Skipped).  Each entry is a dict
      with keys: Ticket_ID, Category, Severity, Status, Response_Time_Secs,
      SLA_Breached, Correlated_With, Confidence_Score.

  data/session_state.json
      A single-key file  {"ticket_index": N}  so that after a Streamlit
      refresh or crash the engineer resumes at the same position in the
      mock_tickets.csv queue instead of starting over from INC-3001.

Rules for this module
---------------------
• No Streamlit imports — functions here must be callable from unit tests
  and from helpers.py without a running Streamlit runtime.
• Never raise on missing files — return safe defaults ([] or 0) instead.
• Called by: helpers.save_and_advance() and app.py on startup.

Functions
---------
  load_processed_tickets() -> list[dict]
      Reads processed_tickets.json; normalises Confidence_Score to str.
  save_processed_tickets(tickets) -> None
      Overwrites processed_tickets.json with the current in-memory list.
  load_ticket_index() -> int
      Reads the saved queue position; returns 0 if the file is missing or corrupt.
  save_ticket_index(index) -> None
      Writes {"ticket_index": N} so the position survives restarts.
"""
import json
import os

PROCESSED_TICKETS_PATH = "data/processed_tickets.json"
SESSION_STATE_PATH      = "data/session_state.json"


def load_processed_tickets() -> list:
    """Load the processed tickets audit log from disk. Returns empty list if missing."""
    if os.path.exists(PROCESSED_TICKETS_PATH):
        with open(PROCESSED_TICKETS_PATH, "r") as f:
            tickets = json.load(f)
        # Ensure Confidence_Score is always str (old records may have int)
        for t in tickets:
            t["Confidence_Score"] = str(t.get("Confidence_Score") or "")
        return tickets
    return []


def save_processed_tickets(tickets: list) -> None:
    """Persist the processed tickets list to disk."""
    with open(PROCESSED_TICKETS_PATH, "w") as f:
        json.dump(tickets, f, indent=2)


def load_ticket_index() -> int:
    """Return the last saved ticket_index (defaults to 0 on missing/corrupt file)."""
    if os.path.exists(SESSION_STATE_PATH):
        try:
            with open(SESSION_STATE_PATH, "r") as f:
                return int(json.load(f).get("ticket_index", 0))
        except (json.JSONDecodeError, ValueError):
            save_ticket_index(0)
    return 0


def save_ticket_index(index: int) -> None:
    """Write ticket_index to disk so it survives Streamlit restarts."""
    with open(SESSION_STATE_PATH, "w") as f:
        json.dump({"ticket_index": int(index)}, f)
