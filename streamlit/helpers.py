"""
helpers.py — Pure utility functions (no Streamlit UI calls)
============================================================

What this file is responsible for
----------------------------------
Three self-contained helpers that are called from app.py.
Because they have zero Streamlit dependencies they can be unit-tested
in isolation without launching a browser or mocking st.session_state
(save_and_advance receives session_state as an explicit argument).

Rules for this module
---------------------
• Never import streamlit — only standard library + constants + persistence.
• Keep each function short and single-purpose.
• Called by: app.py (all three functions).

Functions
---------
  extract_json(raw: str) -> dict
      Robustly pulls a JSON object out of an LLM response that may be
      wrapped in markdown fences (```json … ```) or contain surrounding
      prose.  Three fallback strategies:
        1. Strip fences → json.loads()
        2. Regex search for first {…} block → json.loads()
        3. Return {} (never raises, so the caller always gets a dict)

  get_sla_status(severity: str, start_time: float) -> tuple[float, float, float]
      Given a severity level and the epoch timestamp when the ticket
      entered HITL, returns:
        elapsed_secs   — seconds since HITL started
        remaining_secs — seconds until SLA breach (negative = already breached)
        pct_used       — 0.0–1.0+ fraction of SLA window consumed
      Limit looked up from SLA_THRESHOLDS; defaults to 3600 s if unknown.

  save_and_advance(*, session_state, severity, correlated_with,
                   is_correlated, confidence, status) -> None
      Atomic "finish this ticket" operation called after the engineer
      clicks Approve / Reject / Send / Skip.  Does three things in order:
        1. Appends a result dict to session_state.processed_tickets
           and flushes it to data/processed_tickets.json.
        2. Resets all HITL session_state flags to their idle defaults.
        3. Increments session_state.ticket_index and saves it to disk
           so the queue position survives a page refresh.
"""
import json
import re
import time

from constants import SLA_THRESHOLDS
from persistence import save_processed_tickets, save_ticket_index


# ── JSON extraction ────────────────────────────────────────────────────────────

def extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from LLM output that may contain markdown fences
    or surrounding text.

    Strategy 1: strip markdown fences and parse directly.
    Strategy 2: find the first {...} block with regex.
    Strategy 3: return empty dict (never raises).
    """
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


# ── SLA timer ─────────────────────────────────────────────────────────────────

def get_sla_status(severity: str, start_time: float) -> tuple[float, float, float]:
    """
    Return (elapsed_secs, remaining_secs, pct_used) for a ticket currently at HITL.
    pct_used >= 1.0 means SLA is breached.
    """
    limit     = SLA_THRESHOLDS.get(severity.upper(), 60 * 60)
    elapsed   = time.time() - start_time
    remaining = limit - elapsed
    pct_used  = elapsed / limit
    return elapsed, remaining, pct_used


# ── Ticket save + advance ──────────────────────────────────────────────────────

def save_and_advance(
    *,
    session_state,          # st.session_state passed in from app.py
    severity:        str,
    correlated_with: str,
    is_correlated:   bool,
    confidence,             # int | None
    status:          str,
    pir_path:        str = "",
) -> None:
    """
    Append the current ticket to the processed log, reset HITL session state,
    and increment ticket_index — all in one atomic call.

    Called from app.py after the engineer clicks Approve / Reject / Send / Skip.
    We accept session_state as an explicit parameter so this function stays
    testable without a running Streamlit runtime.
    """
    elapsed_secs = int(time.time() - session_state.sla_start_time) \
                   if session_state.sla_start_time else 0
    sla_limit    = SLA_THRESHOLDS.get(severity.upper(), 3600)

    session_state.processed_tickets.append({
        "Ticket_ID":          session_state.thread_id,
        "Category":           session_state.original_category,
        "Severity":           severity,
        "Status":             status,
        "Response_Time_Secs": elapsed_secs,
        "SLA_Breached":       elapsed_secs > sla_limit,
        "Correlated_With":    correlated_with if is_correlated else "",
        "Confidence_Score":   str(confidence) if confidence is not None else "",
        "PIR_Path":           pir_path,
    })
    save_processed_tickets(session_state.processed_tickets)

    # Reset HITL state
    session_state.waiting_for_user      = False
    session_state.current_node          = "Idle 💤"
    session_state.confidence_score      = None
    session_state.confidence_reason     = ""
    session_state.escalation_sent       = False
    session_state.email_pending         = None

    # Advance queue pointer
    session_state.ticket_index += 1
    save_ticket_index(session_state.ticket_index)
