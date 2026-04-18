"""
Escalation Agent — Emircom NOC
================================
Monitors tickets stuck at HITL (Human-In-The-Loop) beyond the escalation threshold.

If a Critical ticket goes unacknowledged for > 5 minutes, or a High ticket for
> 15 minutes, the agent:
  1. Returns a warning dict with escalation details (UI displays the banner)
  2. Sends an escalation email to the NOC Shift Lead via Gmail SMTP

Called from streamlit/app.py on every SLA-timer rerun — zero background threads,
zero new dependencies, works inside Streamlit's single-threaded model.
"""

import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Escalation thresholds (seconds) ──────────────────────────────────────────
ESCALATION_THRESHOLDS = {
    "CRITICAL": 5  * 60,   #  5 minutes — page immediately
    "HIGH":     15 * 60,   # 15 minutes — notify shift lead
    "MEDIUM":   45 * 60,   # 45 minutes — soft reminder (no email)
}

# Email credentials reused from email_sender config
GMAIL_USER     = os.getenv("GMAIL_USER",         "emircom.noc.agent@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD",  "")
SHIFT_LEAD_EMAIL = os.getenv("SHIFT_LEAD_EMAIL",  GMAIL_USER)  # defaults to same box


# ── Core logic ────────────────────────────────────────────────────────────────

def check_escalation(severity: str, sla_start_time: float, already_escalated: bool) -> dict:
    """
    Check whether this ticket needs escalation.

    Returns a dict:
      {
        "needs_escalation": bool,
        "elapsed_secs":     int,
        "threshold_secs":   int,
        "elapsed_min":      int,
        "threshold_min":    int,
        "severity":         str,
      }
    """
    severity_upper = severity.upper()
    threshold = ESCALATION_THRESHOLDS.get(severity_upper)

    if not sla_start_time or threshold is None or already_escalated:
        return {"needs_escalation": False, "elapsed_secs": 0,
                "threshold_secs": 0, "elapsed_min": 0, "threshold_min": 0,
                "severity": severity_upper}

    elapsed = int(time.time() - sla_start_time)
    return {
        "needs_escalation": elapsed >= threshold,
        "elapsed_secs":     elapsed,
        "threshold_secs":   threshold,
        "elapsed_min":      elapsed // 60,
        "threshold_min":    threshold // 60,
        "severity":         severity_upper,
    }


def send_escalation_email(
    ticket_id:    str,
    severity:     str,
    category:     str,
    affected_node: str,
    elapsed_min:  int,
    threshold_min: int,
    root_cause:   str = "",
    rec_action:   str = "",
) -> bool:
    """
    Send an escalation email to the NOC Shift Lead.
    Returns True if the email was sent successfully, False on any error.
    """
    if not GMAIL_PASSWORD:
        print(f"[ESCALATION] ⚠️ GMAIL_APP_PASSWORD not set — email skipped for {ticket_id}")
        return False

    sev_color = {
        "CRITICAL": "#c0392b",
        "HIGH":     "#e67e22",
        "MEDIUM":   "#f39c12",
    }.get(severity.upper(), "#555")

    sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(severity.upper(), "⚪")

    subject = (
        f"🚨 ESCALATION REQUIRED — {severity.upper()} Ticket {ticket_id} "
        f"unacknowledged for {elapsed_min}m (threshold: {threshold_min}m)"
    )

    html_body = f"""
<html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;">
  <div style="max-width:680px;margin:auto;background:#fff;border-radius:8px;
              overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.12);">

    <!-- Header -->
    <div style="background:#1a3a5c;padding:20px 30px;">
      <h2 style="color:#fff;margin:0;">🛡️ Emircom NOC — Escalation Alert</h2>
      <p style="color:#a8c0d8;margin:4px 0 0;">AI Escalation Agent • Automated Notification</p>
    </div>

    <!-- Urgency Banner -->
    <div style="background:{sev_color};padding:14px 30px;">
      <span style="color:#fff;font-size:18px;font-weight:bold;">
        {sev_emoji} {severity.upper()} TICKET UNACKNOWLEDGED — {elapsed_min} MINUTES
      </span>
    </div>

    <!-- Body -->
    <div style="padding:24px 30px;">
      <p style="font-size:15px;color:#333;">
        The following ticket has been waiting for engineer action for
        <strong style="color:{sev_color};">{elapsed_min} minutes</strong>,
        exceeding the <strong>{threshold_min}-minute</strong> escalation threshold.
        Immediate action is required.
      </p>

      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr style="background:#f0f4f8;">
          <td style="padding:10px;color:#666;width:40%;"><b>Ticket ID</b></td>
          <td style="padding:10px;font-weight:bold;">{ticket_id}</td>
        </tr>
        <tr>
          <td style="padding:10px;color:#666;"><b>Severity</b></td>
          <td style="padding:10px;font-weight:bold;color:{sev_color};">{severity.upper()}</td>
        </tr>
        <tr style="background:#f0f4f8;">
          <td style="padding:10px;color:#666;"><b>Category</b></td>
          <td style="padding:10px;">{category}</td>
        </tr>
        <tr>
          <td style="padding:10px;color:#666;"><b>Affected Node</b></td>
          <td style="padding:10px;"><code style="background:#eee;padding:2px 6px;
              border-radius:3px;">{affected_node}</code></td>
        </tr>
        <tr style="background:#f0f4f8;">
          <td style="padding:10px;color:#666;"><b>Time at HITL</b></td>
          <td style="padding:10px;font-weight:bold;color:{sev_color};">{elapsed_min} minutes</td>
        </tr>
        <tr>
          <td style="padding:10px;color:#666;"><b>Escalation Threshold</b></td>
          <td style="padding:10px;">{threshold_min} minutes</td>
        </tr>
        <tr style="background:#f0f4f8;">
          <td style="padding:10px;color:#666;"><b>Escalated At</b></td>
          <td style="padding:10px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} GST</td>
        </tr>
      </table>

      {"<div style='border-left:4px solid #c0392b;padding:10px 16px;background:#fdf2f2;margin:16px 0;'><b style='color:#c0392b;'>⚡ AI Root Cause</b><p style='margin:6px 0 0;color:#333;'>" + root_cause + "</p></div>" if root_cause else ""}
      {"<div style='border-left:4px solid #27ae60;padding:10px 16px;background:#f0fdf4;margin:16px 0;'><b style='color:#27ae60;'>✅ Recommended Action</b><p style='margin:6px 0 0;color:#333;'>" + rec_action + "</p></div>" if rec_action else ""}

      <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;
                  padding:14px;margin:16px 0;">
        <b>⚠️ Action Required:</b> Log into the Emircom NOC Command Center and
        either <b>Approve & Escalate</b> or <b>Reject</b> this ticket immediately.
      </div>

      <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
      <p style="color:#999;font-size:12px;margin:0;">
        This escalation was triggered automatically by the Emircom NOC Escalation Agent.<br>
        Ticket: <strong>{ticket_id}</strong> — Status: Awaiting Engineer Decision
      </p>
    </div>
  </div>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Emircom NOC Escalation Agent <{GMAIL_USER}>"
    msg["To"]      = SHIFT_LEAD_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, SHIFT_LEAD_EMAIL, msg.as_string())
        print(f"[ESCALATION] ✅ Escalation email sent → {SHIFT_LEAD_EMAIL} "
              f"({ticket_id}, {elapsed_min}m unacknowledged)")
        return True
    except Exception as e:
        print(f"[ESCALATION] ❌ Email error: {type(e).__name__}: {e}")
        return False
