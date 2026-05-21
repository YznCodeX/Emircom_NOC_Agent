"""
email_sender.py
---------------
Sends NOC alert emails directly via Gmail SMTP.
Bypasses GLPI's notification queue entirely.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER     = os.getenv("GMAIL_USER", "emircom.noc.agent@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

NOC_ENGINEER_EMAIL = os.getenv("NOC_ENGINEER_EMAIL", "rifd.project.ai@gmail.com")

TEAM_ROUTING = {
    "Network":     {"team": "NOC Network Team",        "email": NOC_ENGINEER_EMAIL},
    "Security":    {"team": "NOC Security Team (SOC)", "email": NOC_ENGINEER_EMAIL},
    "Hardware":    {"team": "NOC Field Engineering",   "email": NOC_ENGINEER_EMAIL},
    "Cloud":       {"team": "NOC Cloud Team",          "email": NOC_ENGINEER_EMAIL},
    "Application": {"team": "NOC Application Support", "email": NOC_ENGINEER_EMAIL},
}

SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High":     "🟠",
    "Medium":   "🟡",
    "Low":      "🟢",
}

CATEGORY_EMOJI = {
    "Network":     "🌐",
    "Security":    "🔒",
    "Hardware":    "🖥️",
    "Cloud":       "☁️",
    "Application": "📱",
}


def send_alert_email(
    ticket_id: str,
    glpi_ticket_id: str,
    category: str,
    severity: str,
    affected_node: str,
    symptom: str,
    root_cause: str,
    recommended_action: str,
    business_impact: str,
    confidence_score: str,
    correlated_with: str = "",
) -> bool:
    """
    Send a NOC alert email. Returns True if sent, False if failed.
    """
    if not GMAIL_PASSWORD:
        print("  ⚠️ Email skipped — GMAIL_APP_PASSWORD not set in .env")
        return False

    routing   = TEAM_ROUTING.get(category, {"team": "NOC Team", "email": GMAIL_USER})
    team_name = routing["team"]
    to_email  = routing["email"]
    sev_emoji = SEVERITY_EMOJI.get(severity, "⚪")
    cat_emoji = CATEGORY_EMOJI.get(category, "📋")

    subject = f"[NOC ALERT] {sev_emoji} {severity} | {cat_emoji} {category} | {ticket_id} | GLPI #{glpi_ticket_id}"

    corr_line = f"\n<b>Correlated With:</b> {correlated_with}" if correlated_with else ""

    html_body = f"""
<html><body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
  <div style="max-width: 680px; margin: auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

    <!-- Header -->
    <div style="background: #1a3a5c; padding: 20px 30px;">
      <h2 style="color: white; margin: 0;">🛡️ Emircom NOC Alert</h2>
      <p style="color: #a8c0d8; margin: 4px 0 0;">AI-Powered Network Operations Center</p>
    </div>

    <!-- Severity Banner -->
    <div style="background: {'#c0392b' if severity=='Critical' else '#e67e22' if severity=='High' else '#f39c12' if severity=='Medium' else '#27ae60'}; padding: 12px 30px;">
      <span style="color: white; font-size: 18px; font-weight: bold;">{sev_emoji} {severity.upper()} SEVERITY — {category.upper()} INCIDENT</span>
    </div>

    <!-- Ticket Info -->
    <div style="padding: 24px 30px;">
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
        <tr>
          <td style="padding: 8px; color: #666; width: 40%;"><b>NOC Ticket ID</b></td>
          <td style="padding: 8px;">{ticket_id}</td>
        </tr>
        <tr style="background: #f9f9f9;">
          <td style="padding: 8px; color: #666;"><b>GLPI Ticket</b></td>
          <td style="padding: 8px;">#{glpi_ticket_id}</td>
        </tr>
        <tr>
          <td style="padding: 8px; color: #666;"><b>Category</b></td>
          <td style="padding: 8px;">{cat_emoji} {category}</td>
        </tr>
        <tr style="background: #f9f9f9;">
          <td style="padding: 8px; color: #666;"><b>Affected Node</b></td>
          <td style="padding: 8px;"><code style="background:#eee;padding:2px 6px;border-radius:3px;">{affected_node}</code></td>
        </tr>
        <tr>
          <td style="padding: 8px; color: #666;"><b>Assigned Team</b></td>
          <td style="padding: 8px;"><b>{team_name}</b></td>
        </tr>
        <tr style="background: #f9f9f9;">
          <td style="padding: 8px; color: #666;"><b>AI Confidence</b></td>
          <td style="padding: 8px;">{confidence_score}%</td>
        </tr>
        <tr>
          <td style="padding: 8px; color: #666;"><b>Timestamp</b></td>
          <td style="padding: 8px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} GST</td>
        </tr>{corr_line}
      </table>

      <!-- Analysis Sections -->
      <div style="border-left: 4px solid #1a3a5c; padding: 10px 16px; margin: 16px 0; background: #f0f4f8;">
        <b style="color: #1a3a5c;">🔍 Symptom</b>
        <p style="margin: 6px 0 0; color: #333;">{symptom}</p>
      </div>

      <div style="border-left: 4px solid #c0392b; padding: 10px 16px; margin: 16px 0; background: #fdf2f2;">
        <b style="color: #c0392b;">⚡ Root Cause</b>
        <p style="margin: 6px 0 0; color: #333;">{root_cause}</p>
      </div>

      <div style="border-left: 4px solid #e67e22; padding: 10px 16px; margin: 16px 0; background: #fef9f0;">
        <b style="color: #e67e22;">💼 Business Impact</b>
        <p style="margin: 6px 0 0; color: #333;">{business_impact}</p>
      </div>

      <div style="border-left: 4px solid #27ae60; padding: 10px 16px; margin: 16px 0; background: #f0fdf4;">
        <b style="color: #27ae60;">✅ Recommended Action</b>
        <p style="margin: 6px 0 0; color: #333;">{recommended_action}</p>
      </div>

      <!-- Footer -->
      <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
      <p style="color: #999; font-size: 12px; margin: 0;">
        This alert was generated automatically by the Emircom AI NOC Agent.<br>
        View ticket in GLPI: <a href="http://localhost/front/ticket.form.php?id={glpi_ticket_id}">GLPI #{glpi_ticket_id}</a>
      </p>
    </div>
  </div>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Emircom NOC Agent <{GMAIL_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"  📧 Email sent → {to_email} ({severity} | {ticket_id})")
        return True
    except Exception as e:
        print(f"  ⚠️ Email failed: {e}")
        return False
