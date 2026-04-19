"""
constants.py — Shared lookup tables for the Streamlit app
==========================================================

What this file is responsible for
----------------------------------
One place for every "magic value" used across the NOC dashboard.
If a threshold, label, colour, or routing address needs to change,
edit it here — every module that imports it picks up the change
automatically.

Rules for this module
---------------------
• No imports of any kind — pure Python data only.
• No Streamlit, no src.*, no pandas — safe to import anywhere.
• Used by: app.py, helpers.py, reports.py, chatbot.py.

Contents
--------
  SLA_THRESHOLDS   dict[str, int]
      How many seconds an engineer has to act before an SLA breach,
      keyed by severity string (upper-case):
        CRITICAL → 15 min  |  HIGH → 1 hr  |  MEDIUM → 4 hr  |  LOW → 24 hr

  CATEGORY_ICONS   dict[str, str]
      Maps category name → display emoji used in UI labels and reports.

  SEVERITY_COLORS  dict[str, str]
      Maps severity → coloured dot emoji for quick visual scanning.

  TEAM_ROUTING     dict[str, dict]
      Maps category → {"team": "…", "lead": "…", "email": "…"}
      Used in the email notification panel and in remedy_node when
      composing the escalation email subject/body.
"""

# How long (seconds) an engineer has to act on a ticket before SLA breach
SLA_THRESHOLDS = {
    "CRITICAL": 15 * 60,       #  15 minutes
    "HIGH":     60 * 60,       #   1 hour
    "MEDIUM":   4  * 60 * 60,  #   4 hours
    "LOW":      24 * 60 * 60,  #  24 hours
}

# Category → display emoji
CATEGORY_ICONS = {
    "Network":     "🌐",
    "Security":    "🔒",
    "Hardware":    "🖥️",
    "Cloud":       "☁️",
    "Application": "📱",
}

# Severity → colored dot emoji
SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🟢",
}

# Category → team contact info (used in email panel + remedy node)
TEAM_ROUTING = {
    "Network":     {"team": "Network Operations Team",    "lead": "Sr. Network Engineer",    "email": "network-ops@emircom.com"},
    "Security":    {"team": "Security Operations (SOC)",  "lead": "Sr. SOC Analyst",         "email": "soc-team@emircom.com"},
    "Hardware":    {"team": "Field Engineering Team",     "lead": "Sr. Field Engineer",       "email": "field-eng@emircom.com"},
    "Cloud":       {"team": "Cloud Infrastructure Team",  "lead": "Sr. Cloud Engineer",       "email": "cloud-ops@emircom.com"},
    "Application": {"team": "Application Support Team",   "lead": "Sr. App Support Engineer", "email": "app-support@emircom.com"},
}
