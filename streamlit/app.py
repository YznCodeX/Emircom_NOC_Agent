"""
app.py — Emircom NOC & SOC Command Center (Streamlit entry point)
=================================================================

This is the main UI file.  Run it with:
    venv\\Scripts\\streamlit run streamlit/app.py

What this file is responsible for
----------------------------------
• Bootstrapping sys.path so that `src.*` imports (agent_graph, etc.) work
  regardless of which directory Streamlit is launched from.
• Initialising every st.session_state key exactly once on first load.
• Rendering the three-tab layout and wiring the sidebar controls.
• Driving the HITL (Human-In-The-Loop) ticket review cycle:
    1. analyze_current_ticket()  — invokes the LangGraph pipeline, pauses at
                                   the "remedy" or "drop" interrupt.
    2. HITL panel (Tab 1)        — shows the AI analysis, runbook, email draft,
                                   SLA countdown, and Approve / Reject buttons.
    3. Email notification panel  — second confirmation step after Approve.
    4. save_and_advance()        — logs the result and moves to the next ticket.
• Providing helper functions that depend on `df` (the live DataFrame) and
  therefore cannot be moved to sibling modules:
    - analyze_current_ticket()
    - get_pending_tickets()
    - (queue stats, dedup reset, etc.)

Tab layout
----------
  Tab 1 — Operations Center   HITL panel + live pending-queue table
  Tab 2 — Analytics Dashboard Plotly charts, Word/Excel handoff report
  Tab 3 — NOC AI Chatbot      Streaming LLM assistant with log-paste support

Sibling modules (imported here, kept separate for clarity)
-----------------------------------------------------------
  persistence.py  — disk I/O only  (processed_tickets.json, session_state.json)
  constants.py    — static lookup tables (SLA_THRESHOLDS, TEAM_ROUTING, …)
  helpers.py      — pure functions  (extract_json, get_sla_status, save_and_advance)
  reports.py      — Word .docx and Excel .xlsx generators, no Streamlit calls
  chatbot.py      — full Tab 3 render function (render_chatbot_tab)

Key session_state flags
-----------------------
  waiting_for_user      True while the HITL panel is showing
  email_confirm_pending True while the email notification panel is showing
  ticket_index          Current position in the mock_tickets.csv queue
  sla_start_time        epoch float — when the ticket entered HITL
  escalation_sent       bool — prevents duplicate escalation emails per ticket
"""

# ── Path bootstrap (so `src.*` imports work from any working directory) ────────
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Standard library ──────────────────────────────────────────────────────────
import json
import os
import time
from datetime import datetime

# ── Third-party ───────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px

# ── Local modules (same streamlit/ directory) ─────────────────────────────────
from persistence import (
    load_processed_tickets, save_processed_tickets,
    load_ticket_index,      save_ticket_index,
)
from constants import (
    SLA_THRESHOLDS, CATEGORY_ICONS, SEVERITY_COLORS, TEAM_ROUTING,
)
from helpers  import extract_json, get_sla_status, save_and_advance
from reports  import (
    run_handoff_llm, generate_handoff_report_doc, generate_excel_report,
    generate_pir_doc,
)
from chatbot  import render_chatbot_tab

# ── Agent graph (LangGraph pipeline) ─────────────────────────────────────────
from src.agent_graph import app as noc_app   # renamed to avoid shadowing st.app

# ═════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Emircom NOC AI Agent", page_icon="🛡️", layout="wide")

# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE — initialise every key once on first load
# ═════════════════════════════════════════════════════════════════════════════
_defaults = {
    "ticket_index":         load_ticket_index(),
    "thread_id":            "",
    "waiting_for_user":     False,
    "analysis_result":      "",
    "current_node":         "Idle 💤",
    "processed_tickets":    load_processed_tickets(),
    "original_category":    "",
    "sla_start_time":       None,
    "confidence_score":     None,
    "confidence_reason":    "",
    "queue_scan_results":   [],
    "queue_filter":         "All",
    "escalation_sent":      False,
    "handoff_doc_buf":      None,
    "handoff_ready":        False,
    "excel_report_cache":   None,   # bytes — regenerated only when ticket count changes
    "excel_report_len":     -1,
    "chat_history":         [],
    "paste_logs_open":      False,
    "pasted_logs":          "",
    "email_pending":        None,   # dict with tid/cat/sev/node/team when panel active, else None
    "trend_insight":        "",     # amber banner text after ticket approval — cleared on dismiss
    "shift_briefing":       "",     # cached LLM shift briefing text
    "shift_briefing_len":   -1,     # queue length when briefing was last generated
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🛡️ NOC Command Center")
    st.caption(f"🕐 {datetime.now().strftime('%d %b %Y  %H:%M:%S')}")
    st.divider()

    st.markdown("#### 📡 Data Source")
    data_source = st.radio(
        "Alert feed:",
        ["Mock CSV", "Cisco DNA Center", "Both"],
        index=0,
        help="Mock CSV = sample data  |  DNA Center = live Cisco sandbox  |  Both = combined",
    )
    if data_source in ("Cisco DNA Center", "Both"):
        if st.button("🔄 Refresh Live Data", width="stretch"):
            st.session_state.pop("dnac_alerts_cache", None)

    st.divider()
    st.markdown("#### 📂 Current Node")
    st.info(st.session_state.current_node)
    st.divider()
    st.file_uploader("Upload Logs File (.csv, .txt)", type=["csv", "txt"])

# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADING — mock CSV and/or live DNA Center alerts
# ═════════════════════════════════════════════════════════════════════════════

def _load_dnac_alerts() -> list:
    """Fetch live alerts from Cisco DNA Center (cached in session state for this run)."""
    if "dnac_alerts_cache" not in st.session_state:
        try:
            from cisco.devnet_connector import get_live_alerts
            alerts = get_live_alerts()
            for a in alerts:
                a.setdefault("Severity", "Medium")
            st.session_state.dnac_alerts_cache = alerts
        except Exception as e:
            st.session_state.dnac_alerts_cache = []
            st.warning(f"DNA Center unavailable: {e}")
    return st.session_state.dnac_alerts_cache


try:
    mock_df = pd.read_csv("data/mock_tickets.csv")
except FileNotFoundError:
    mock_df = pd.DataFrame([{
        "Ticket_ID": "INC-1001", "Category": "Network",
        "Alert_Message": "High CPU utilization", "Raw_Logs": "CPU at 99%",
    }])

if data_source == "Mock CSV":
    df = mock_df
elif data_source == "Cisco DNA Center":
    dnac_alerts = _load_dnac_alerts()
    df = pd.DataFrame(dnac_alerts) if dnac_alerts else pd.DataFrame(columns=mock_df.columns)
    if df.empty:
        st.info("No active alerts from DNA Center — all devices healthy.")
else:  # Both
    dnac_alerts = _load_dnac_alerts()
    dnac_df = pd.DataFrame(dnac_alerts) if dnac_alerts else pd.DataFrame(columns=mock_df.columns)
    df = pd.concat([mock_df, dnac_df], ignore_index=True).drop_duplicates(subset="Ticket_ID")

# ═════════════════════════════════════════════════════════════════════════════
# QUEUE HELPERS  (depend on `df`, so they live here)
# ═════════════════════════════════════════════════════════════════════════════

def get_processed_ids() -> set:
    return {t["Ticket_ID"] for t in st.session_state.processed_tickets}


def get_pending_tickets() -> list:
    processed = get_processed_ids()
    return df[~df["Ticket_ID"].isin(processed)].to_dict("records")


def batch_scan_queue() -> list:
    """LLM quick-triage of all pending tickets — returns list of dicts."""
    from src.agent_graph import llm
    pending = get_pending_tickets()
    if not pending:
        return []
    ticket_list = "\n".join([
        f"- {t['Ticket_ID']} | {t['Category']} | {t['Alert_Message']}"
        for t in pending
    ])
    prompt = f"""You are a NOC shift lead at Emircom. Quickly triage these pending alerts.

For each ticket determine:
1. Severity: Critical / High / Medium / Low
2. Alert type: "Device Down" / "Link Down" / "Resource Down" / "Security Alert" / "Performance" / "Other"
3. Summary: max 12 words, technical, no filler
4. Group: same letter (A, B, C…) for tickets sharing the same root cause. Use "—" if standalone.

PENDING TICKETS:
{ticket_list}

Reply ONLY with a valid JSON array, no markdown:
[{{"ticket_id":"...","severity":"...","alert_type":"...","summary":"...","group":"..."}}]"""

    response = llm.invoke(prompt)
    raw = response.content.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ═════════════════════════════════════════════════════════════════════════════
# SHIFT BRIEFING  — LLM one-liner summary cached until queue length changes
# ═════════════════════════════════════════════════════════════════════════════

def get_shift_briefing(pending: list) -> str:
    """
    Generate a 1-2 sentence NOC shift briefing using the LLM.
    Result is cached in session_state and only regenerated when queue length changes.
    Returns empty string if pending is empty.
    """
    if not pending:
        return ""

    # Return cached version if queue hasn't changed
    if (st.session_state.shift_briefing_len == len(pending)
            and st.session_state.shift_briefing):
        return st.session_state.shift_briefing

    from collections import Counter
    from src.agent_graph import llm as _llm

    crit  = sum(1 for t in pending if t.get("Severity") == "Critical")
    high  = sum(1 for t in pending if t.get("Severity") == "High")
    med   = sum(1 for t in pending if t.get("Severity") == "Medium")
    low   = sum(1 for t in pending if t.get("Severity") == "Low")

    nodes = [str(t.get("Affected_Node", "")).strip() for t in pending
             if t.get("Affected_Node") and str(t.get("Affected_Node")).strip() not in ("", "nan", "—")]
    node_counts = Counter(nodes).most_common(3)
    hotspots    = ", ".join(f"{n} ({c}×)" for n, c in node_counts if c >= 2) or "none"
    next_up     = pending[0].get("Ticket_ID", "—")

    prompt = (
        "You are a NOC shift lead at Emircom. Write a concise 1-2 sentence shift briefing "
        "for an engineer starting their session. Be direct — no greetings, no filler.\n\n"
        f"Queue stats: {len(pending)} total | {crit} Critical | {high} High | {med} Medium | {low} Low\n"
        f"Repeated devices (possible shared root cause): {hotspots}\n"
        f"First ticket in queue: {next_up}\n\n"
        "Example style: \"32 alerts pending — 4 Critical. CE-MPLS-01 appears 3 times, "
        "investigate as shared root cause. Start with INC-3001.\""
    )

    try:
        resp = _llm.invoke(prompt)
        text = resp.content.strip()
    except Exception:
        text = (f"{len(pending)} alerts pending — {crit} Critical, {high} High. "
                f"Start with {next_up}.")

    st.session_state.shift_briefing     = text
    st.session_state.shift_briefing_len = len(pending)
    return text


# ═════════════════════════════════════════════════════════════════════════════
# TREND ANALYSIS  — pattern detector over last N resolved tickets
# ═════════════════════════════════════════════════════════════════════════════

def check_trends(processed: list) -> str:
    """
    Analyse the last 10 processed tickets for patterns (category spikes, repeated devices,
    severity clusters, correlated tickets).
    Returns a one-sentence insight prefixed with "⚠️ Trend:" or "" if no pattern found.
    Requires at least 3 processed tickets before running.
    """
    if len(processed) < 3:
        return ""

    recent  = processed[-10:]
    summary = "\n".join(
        f"- {t.get('Ticket_ID','?')} | {t.get('Category','?')} | "
        f"{t.get('Severity','?')} | correlated_with={t.get('Correlated_With','none')}"
        for t in recent
    )

    from src.agent_graph import llm as _llm

    prompt = (
        "You are a NOC analyst at Emircom. Examine these recently resolved tickets "
        "and identify if there is a meaningful trend worth flagging.\n\n"
        f"Recent tickets (oldest first):\n{summary}\n\n"
        "Rules:\n"
        "- If the same category appears 3+ times → flag it.\n"
        "- If 2+ tickets share a correlated_with value → flag it.\n"
        "- If Critical/High severity spikes (3+ in a row) → flag it.\n"
        "- If there is NO clear pattern → reply with exactly: NO_TREND\n\n"
        "When a pattern exists write ONE sentence starting with '⚠️ Trend:'. "
        "Be specific (mention ticket IDs or category). No filler."
    )

    try:
        resp = _llm.invoke(prompt)
        text = resp.content.strip()
    except Exception:
        return ""

    if "NO_TREND" in text:
        return ""
    return text


# ═════════════════════════════════════════════════════════════════════════════
# TICKET ANALYZER  (depends on `df` and `noc_app`, so lives here)
# ═════════════════════════════════════════════════════════════════════════════

def analyze_current_ticket(specific_ticket: dict | None = None) -> None:
    """
    Run the LangGraph pipeline on the next unprocessed ticket (or a specific one).
    Pauses at the HITL interrupt and sets session state so the UI can render the panel.
    """
    if specific_ticket is not None:
        match = df[df["Ticket_ID"] == specific_ticket["Ticket_ID"]]
        if not match.empty:
            st.session_state.ticket_index = match.index[0]
            save_ticket_index(st.session_state.ticket_index)
        ticket = pd.Series(specific_ticket)
    else:
        # Skip tickets already in the processed log
        processed = get_processed_ids()
        while st.session_state.ticket_index < len(df):
            if df.iloc[st.session_state.ticket_index]["Ticket_ID"] not in processed:
                break
            st.session_state.ticket_index += 1
            save_ticket_index(st.session_state.ticket_index)

        if st.session_state.ticket_index >= len(df):
            st.session_state.ticket_index = 0
            save_ticket_index(0)
            return

        ticket = df.iloc[st.session_state.ticket_index]

    st.session_state.thread_id          = ticket["Ticket_ID"]
    st.session_state.original_category  = ticket["Category"]
    st.session_state.email_pending = None   # always clear when a new ticket loads
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    inputs = {
        "ticket_id":   ticket["Ticket_ID"],
        "category":    ticket["Category"],
        "description": ticket.get("Alert_Message", ""),
        "logs":        ticket.get("Raw_Logs",       ""),
    }

    with st.spinner(f"🤖 Analyzing {ticket['Ticket_ID']}..."):
        noc_app.invoke(inputs, config=config)
        state = noc_app.get_state(config)

        if state.next and state.next[0] in ["remedy", "drop"]:
            st.session_state.waiting_for_user  = True
            st.session_state.sla_start_time    = time.time()
            st.session_state.escalation_sent   = False
            action = "Ticket Creation" if state.next[0] == "remedy" else "DROP Duplicate"
            st.session_state.current_node      = f"⏳ HITL: {action}"
            st.session_state.analysis_result   = state.values.get("analysis", "")
            st.session_state.confidence_score  = state.values.get("confidence_score", None)

            # Pre-parse confidence reason so it's ready for the HITL panel
            try:
                raw_cr = st.session_state.analysis_result.replace("```json","").replace("```","").strip()
                parsed_cr = extract_json(raw_cr)
                st.session_state.confidence_reason = parsed_cr.get("Confidence_Reason", "")
            except Exception:
                st.session_state.confidence_reason = ""


# ═════════════════════════════════════════════════════════════════════════════
# PAGE HEADER + TABS
# ═════════════════════════════════════════════════════════════════════════════
st.title("🛡️ Emircom NOC & SOC Command Center")
tab1, tab2, tab3 = st.tabs(["🚀 Operations Center", "📊 Analytics Dashboard", "🤖 NOC Chatbot"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — OPERATIONS CENTER
# ═════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Live stats strip ──────────────────────────────────────────────────────
    total_processed = len(st.session_state.processed_tickets)
    approved_count  = sum(1 for t in st.session_state.processed_tickets if t["Status"] == "Approved")
    dropped_count   = sum(1 for t in st.session_state.processed_tickets if t["Status"] == "Dropped (Duplicate)")
    rejected_count  = sum(1 for t in st.session_state.processed_tickets if t["Status"] == "Rejected")
    sla_breached    = sum(1 for t in st.session_state.processed_tickets if t.get("SLA_Breached", False))
    queue_remaining = max(0, len(df) - st.session_state.ticket_index)

    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("📋 In Queue",     queue_remaining)
    s2.metric("🤖 Processed",   total_processed)
    s3.metric("✅ Approved",     approved_count)
    s4.metric("🗑️ Duplicates",  dropped_count)
    s5.metric("❌ Rejected",     rejected_count)
    s6.metric("🚨 SLA Breached", sla_breached)

    if st.button("🚀 Scan Next", type="primary", width="content",
                 disabled=st.session_state.waiting_for_user):
        analyze_current_ticket()
        st.rerun()

    st.divider()

    # ── Trend Analysis banner (amber) — shown after ticket approval ───────────
    if st.session_state.trend_insight:
        _tc, _td = st.columns([11, 1])
        with _tc:
            st.markdown(
                f"<div style='background:rgba(245,158,11,0.10);border-left:4px solid #f59e0b;"
                f"border-radius:6px;padding:10px 16px;margin-bottom:10px;font-size:14px;'>"
                f"{st.session_state.trend_insight}</div>",
                unsafe_allow_html=True,
            )
        with _td:
            if st.button("✕", key="dismiss_trend", help="Dismiss"):
                st.session_state.trend_insight = ""
                st.rerun()

    # ── Shift Briefing banner (blue) — shown when queue is idle ──────────────
    if not st.session_state.waiting_for_user:
        _pending_for_brief = get_pending_tickets()
        if _pending_for_brief:
            _briefing = get_shift_briefing(_pending_for_brief)
            if _briefing:
                st.markdown(
                    f"<div style='background:rgba(59,130,246,0.08);border-left:4px solid #3b82f6;"
                    f"border-radius:6px;padding:10px 16px;margin-bottom:10px;font-size:14px;'>"
                    f"🌅 <b>Shift Briefing</b> &nbsp;—&nbsp; {_briefing}</div>",
                    unsafe_allow_html=True,
                )

    # ── HITL Panel ────────────────────────────────────────────────────────────
    if st.session_state.waiting_for_user:

        if st.button("← Back to Queue", type="secondary", width="content"):
            st.session_state.waiting_for_user      = False
            st.session_state.current_node          = "Idle 💤"
            st.session_state.analysis_result       = ""
            st.session_state.confidence_score      = None
            st.session_state.confidence_reason     = ""
            st.session_state.escalation_sent       = False
            st.session_state.email_pending         = None
            st.rerun()

        # Parse analysis JSON from LLM output
        try:
            parsed        = extract_json(st.session_state.analysis_result)
            severity      = parsed.get("Severity",           "Unknown")
            category      = parsed.get("Categorization",     "Unknown")
            affected_node = parsed.get("Affected_Node",       "N/A")
            root_cause    = parsed.get("Root_Cause",          "N/A")
            biz_impact    = parsed.get("Business_Impact",     "N/A")
            symptom       = parsed.get("Symptom_Description", "N/A")
            rec_action    = parsed.get("Recommended_Action",  "Review logs")
            is_drop       = "DROP ALERT" in rec_action
            if not parsed:
                raise ValueError("empty")
        except Exception:
            st.info("ℹ️ Showing raw agent output — could not extract structured fields.")
            severity = category = "Unknown"
            affected_node = root_cause = biz_impact = symptom = rec_action = "N/A"
            is_drop = False

        # Pull correlated state from LangGraph checkpoint
        config_check    = {"configurable": {"thread_id": st.session_state.thread_id}}
        agent_state     = noc_app.get_state(config_check)
        is_correlated   = agent_state.values.get("is_correlated", False)
        correlated_with = agent_state.values.get("correlated_with", "")

        # Confidence: prefer session state (set at analysis time), fall back to checkpoint
        confidence  = st.session_state.confidence_score
        conf_reason = st.session_state.confidence_reason
        if confidence is None:
            confidence = agent_state.values.get("confidence_score", None)
            if confidence is not None:
                try:
                    conf_reason = extract_json(st.session_state.analysis_result).get("Confidence_Reason", "")
                except Exception:
                    conf_reason = ""

        team_info    = TEAM_ROUTING.get(
            st.session_state.original_category,
            {"team": "NOC Tier-2", "lead": "NOC Shift Lead", "email": "noc-support@emircom.com"},
        )
        remedy_ticket = f"REM-{st.session_state.thread_id.replace('INC-', '')}-{datetime.now().strftime('%H%M')}"
        sev_icon      = SEVERITY_COLORS.get(severity.upper(), "⚪")
        cat_icon      = CATEGORY_ICONS.get(st.session_state.original_category, "📋")

        # ── Ticket header card ────────────────────────────────────────────────
        header = (
            f"{sev_icon} &nbsp; **{severity.upper()}** &nbsp;|&nbsp; "
            f"`{st.session_state.thread_id}` &nbsp;|&nbsp; "
            f"{cat_icon} {st.session_state.original_category} &nbsp;|&nbsp; "
            f"📍 {affected_node}"
        )
        if severity.upper() == "CRITICAL":
            st.error(header)
        elif severity.upper() == "HIGH":
            st.warning(header)
        elif severity.upper() == "MEDIUM":
            st.info(header)
        else:
            st.success(header)

        # ── Pipeline progress bar ─────────────────────────────────────────────
        if st.session_state.get("email_pending"):
            hitl_step  = "<span>✅ HITL</span>"
            email_step = "<span style='color:#ccc'>──▶</span><span style='font-weight:bold;color:#1a3a5c'>⏳ Email?</span>"
        else:
            hitl_step  = "<span style='font-weight:bold;color:#d62728'>⏳ HITL</span>"
            email_step = ""

        st.markdown(
            "<div style='display:flex;justify-content:space-between;align-items:center;"
            "background:#f0f2f6;border-radius:8px;padding:8px 16px;font-size:13px;margin-bottom:4px'>"
            "<span>✅ Triage</span><span style='color:#ccc'>──▶</span>"
            "<span>✅ Dedup</span><span style='color:#ccc'>──▶</span>"
            "<span>✅ Analysis</span><span style='color:#ccc'>──▶</span>"
            "<span>✅ Runbook</span><span style='color:#ccc'>──▶</span>"
            "<span>✅ Correlation</span><span style='color:#ccc'>──▶</span>"
            f"{hitl_step}{email_step}"
            "</div>",
            unsafe_allow_html=True,
        )

        if is_correlated and correlated_with:
            st.warning(f"🔗 **Root Cause Correlation** — Shares root cause with: **{correlated_with}** — Investigate as one incident before escalating separately.")

        if "DEDUP_WARN" in rec_action or "DEDUP_ERROR" in rec_action:
            st.warning("⚠️ Deduplication engine failed — ticket passed through unverified. Manual duplicate check recommended.")

        # ── Escalation agent ──────────────────────────────────────────────────
        if not is_drop and st.session_state.sla_start_time:
            try:
                from src.escalation_agent import check_escalation, send_escalation_email
                esc = check_escalation(
                    severity          = severity,
                    sla_start_time    = st.session_state.sla_start_time,
                    already_escalated = st.session_state.escalation_sent,
                )
                if esc["needs_escalation"]:
                    send_escalation_email(
                        ticket_id     = st.session_state.thread_id,
                        severity      = severity,
                        category      = st.session_state.original_category,
                        affected_node = affected_node,
                        elapsed_min   = esc["elapsed_min"],
                        threshold_min = esc["threshold_min"],
                        root_cause    = root_cause,
                        rec_action    = rec_action,
                    )
                    st.session_state.escalation_sent = True
                    st.markdown(
                        f"<div style='background:#c0392b;color:#fff;padding:14px 20px;"
                        f"border-radius:8px;margin-bottom:8px;animation:pulse 1s infinite;'>"
                        f"<b>🚨 ESCALATION TRIGGERED</b> — {severity.upper()} ticket "
                        f"<code style='color:#ffd;'>{st.session_state.thread_id}</code> "
                        f"has been at HITL for <b>{esc['elapsed_min']} minutes</b> "
                        f"(threshold: {esc['threshold_min']}m) — Escalation email sent ✉️</div>"
                        f"<style>@keyframes pulse{{0%{{opacity:1}}50%{{opacity:0.7}}100%{{opacity:1}}}}</style>",
                        unsafe_allow_html=True,
                    )
                elif st.session_state.escalation_sent:
                    st.markdown(
                        f"<div style='background:#7f1d1d;color:#fca5a5;padding:10px 16px;"
                        f"border-radius:6px;margin-bottom:6px;font-size:13px;'>"
                        f"🚨 <b>Escalated</b> — Shift Lead notified {esc['elapsed_min']}m ago.</div>",
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass   # never let escalation agent crash the HITL panel

        st.divider()

        # ── 2-column split: left = analysis tabs, right = action panel ────────
        left_col, right_col = st.columns([6, 4])
        runbook_text = agent_state.values.get("runbook_match", "")

        with left_col:
            tab_sum, tab_logs, tab_rb, tab_email = st.tabs(
                ["📋 Summary", "📜 Raw Logs", "📖 Runbook", "📧 Email Template"]
            )

            with tab_sum:
                summary_df = pd.DataFrame({
                    "Field":   ["Categorization", "Affected Node", "Severity",
                                "Business Impact", "Symptom", "Root Cause", "Recommended Action"],
                    "Details": [category, affected_node, severity,
                                biz_impact, symptom, root_cause, rec_action],
                })
                st.dataframe(summary_df, hide_index=True, width="stretch", height=280)

            with tab_logs:
                raw_logs = "No logs available."
                if st.session_state.ticket_index < len(df):
                    raw_logs = df.iloc[st.session_state.ticket_index].get("Raw_Logs", "No logs available.")
                st.code(raw_logs, language=None)

            with tab_rb:
                supervisor_reason = agent_state.values.get("supervisor_reason", "")
                if runbook_text:
                    if supervisor_reason:
                        st.caption(f"🎯 **Supervisor routing:** _{supervisor_reason}_")
                    st.markdown(runbook_text)
                    st.divider()
                    st.caption("📌 Runbook sourced from Emircom NOC runbook library.")
                else:
                    st.info("📖 No runbook matched this alert with sufficient confidence (threshold: 50%).\n\n"
                            "Check the **Summary** tab for AI-generated recommended action.")
                    if supervisor_reason:
                        st.caption(f"🎯 **Supervisor routing:** _{supervisor_reason}_")

            with tab_email:
                email_body = f"""To: {team_info['email']}
Subject: [{severity.upper()}] Incident {st.session_state.thread_id} — {st.session_state.original_category} Alert

Dear {team_info['team']},

Please find below the incident details requiring your immediate attention.

+----------------------+------------------------------------------+
| Field                | Details                                  |
+----------------------+------------------------------------------+
| Ticket ID            | {st.session_state.thread_id:<40} |
| Remedy Ticket        | {remedy_ticket:<40} |
| Date & Time          | {datetime.now().strftime('%d-%b-%Y %H:%M'):<40} |
| Severity             | {severity.upper():<40} |
| Category             | {st.session_state.original_category:<40} |
| Affected Device      | {affected_node:<40} |
| Issue Description    | {rec_action[:40]:<40} |
| Assigned To          | {team_info['lead']:<40} |
| Reported By          | NOC AI Agent — Emircom                   |
+----------------------+------------------------------------------+

Please acknowledge receipt and provide an ETA for resolution.

Regards,
NOC Operations Center
Emircom"""
                st.code(email_body, language=None)
                st.caption("Copy and send if the team requires email notification.")

        with right_col:
            with st.container(border=True):

                # Decision buttons
                if is_drop:
                    st.error("🛑 **DUPLICATE DETECTED**")
                    st.caption(rec_action)
                    btn_approve_label = "✅ Approve Drop"
                    status_to_save    = "Dropped (Duplicate)"
                else:
                    btn_approve_label = "✅ Approve & Escalate"
                    status_to_save    = "Approved"

                b1, b2 = st.columns(2)
                approve_clicked = b1.button(btn_approve_label, type="primary", width="stretch")
                reject_clicked  = b2.button("❌ Reject",                        width="stretch")

                st.divider()

                # SLA timer
                if st.session_state.sla_start_time and severity.upper() not in ("UNKNOWN", ""):
                    elapsed, remaining, pct_used = get_sla_status(severity, st.session_state.sla_start_time)
                    sla_limit = SLA_THRESHOLDS.get(severity.upper(), 3600)
                    if remaining <= 0:
                        st.error("🚨 SLA BREACHED")
                    else:
                        mins_r = int(remaining // 60)
                        secs_r = int(remaining % 60)
                        mins_e = int(elapsed  // 60)
                        secs_e = int(elapsed  %  60)
                        sla_text = f"⏱️ SLA — {mins_r}m {secs_r}s left  (elapsed {mins_e}m {secs_e}s / {sla_limit // 60}m)"
                        if pct_used >= 0.75:
                            st.warning(f"⚠️ {mins_r}m {secs_r}s remaining", icon=None)
                        st.progress(min(pct_used, 1.0), text=sla_text)

                # Confidence score
                if confidence is not None and not is_drop:
                    if confidence >= 85:
                        conf_label = f"🎯 Confidence — ✅ {confidence}% High"
                    elif confidence >= 60:
                        conf_label = f"🎯 Confidence — ⚠️ {confidence}% Moderate"
                    else:
                        conf_label = f"🎯 Confidence — 🔴 {confidence}% Low"
                    st.progress(confidence / 100, text=conf_label)
                    if conf_reason:
                        st.caption(f"_{conf_reason}_")

                st.divider()

                # Remedy + team info
                if not is_drop:
                    escalation_badge = ""
                    if severity.upper() == "CRITICAL":
                        escalation_badge = "🚨 On-Call Paged"
                    elif severity.upper() == "HIGH":
                        escalation_badge = "🟠 Lead Notified"
                    st.markdown(
                        f"<div style='font-size:13px;line-height:1.8'>"
                        f"<b>🎫</b> <code>{remedy_ticket}</code><br>"
                        f"<b>👥</b> {team_info['team']}<br>"
                        f"<b>📧</b> <code>{team_info['email']}</code><br>"
                        + (f"<b>{escalation_badge}</b>" if escalation_badge else "")
                        + "</div>",
                        unsafe_allow_html=True,
                    )

            # ── Button handlers ───────────────────────────────────────────────
            if approve_clicked:
                if is_drop:
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    noc_app.invoke(None, config=config)
                    save_and_advance(
                        session_state=st.session_state, severity=severity,
                        correlated_with=correlated_with, is_correlated=is_correlated,
                        confidence=confidence, status=status_to_save,
                    )
                    analyze_current_ticket()
                    st.rerun()
                else:
                    # Single atomic snapshot — tid ties the panel to this exact ticket
                    st.session_state.email_pending = {
                        "tid":  st.session_state.thread_id,
                        "cat":  st.session_state.original_category,
                        "sev":  severity,
                        "node": affected_node,
                        "team": team_info,
                    }
                    st.rerun()

            if reject_clicked:
                save_and_advance(
                    session_state=st.session_state, severity=severity,
                    correlated_with=correlated_with, is_correlated=is_correlated,
                    confidence=confidence, status="Rejected",
                )
                try:
                    _trend = check_trends(st.session_state.processed_tickets)
                    if _trend:
                        st.session_state.trend_insight = _trend
                except Exception:
                    pass
                analyze_current_ticket()
                st.rerun()

        # ── Email notification step ───────────────────────────────────────────
        # email_pending is a dict with tid/cat/sev/node/team, set atomically at
        # approve-click. Panel only shows if the stored tid still matches the
        # current ticket — so it can never ghost onto the next ticket.
        _ep = st.session_state.get("email_pending")
        if _ep and _ep.get("tid") != st.session_state.thread_id:
            st.session_state.email_pending = None
            _ep = None

        if _ep and not is_drop:
            _snap_tid  = _ep["tid"]
            _snap_cat  = _ep["cat"]
            _snap_sev  = _ep["sev"]
            _snap_node = _ep["node"]
            _snap_team = _ep["team"]

            _sev_upper    = _snap_sev.upper()
            _accent_color = {"CRITICAL": "#ef5350", "HIGH": "#ffa726",
                             "MEDIUM": "#ffee58", "LOW": "#66bb6a"}.get(_sev_upper, "#7986cb")
            _sev_emoji    = {"CRITICAL": "🔴", "HIGH": "🟠",
                             "MEDIUM": "🟡", "LOW": "🟢"}.get(_sev_upper, "⚪")
            _subj = f"[{_sev_upper}] {_snap_tid} — {_snap_cat} Alert"

            st.markdown(
                f"<div style='height:3px;background:{_accent_color};"
                f"border-radius:2px;margin:8px 0 16px 0'></div>",
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.markdown("##### 📬 &nbsp;Notify the team?")
                st.caption("GLPI ticket is created either way — this controls the email only")
                st.divider()

                rc1, rc2 = st.columns([1, 3])
                rc1.markdown("**To**")
                rc2.code(_snap_team["email"], language=None)

                rc1, rc2 = st.columns([1, 3])
                rc1.markdown("**Subject**")
                rc2.markdown(f"{_sev_emoji} &nbsp;`{_subj}`")

                rc1, rc2 = st.columns([1, 3])
                rc1.markdown("**Team**")
                rc2.markdown(f"**{_snap_team['team']}**")

                rc1, rc2 = st.columns([1, 3])
                rc1.markdown("**Node**")
                rc2.code(_snap_node, language=None)

                if _sev_upper == "CRITICAL":
                    st.error("🚨 **CRITICAL** — Immediate notification recommended", icon="🚨")
                elif _sev_upper == "HIGH":
                    st.warning("⚠️ **HIGH** severity — Recommended to notify", icon="⚠️")
                else:
                    st.info("ℹ️ Notify team or skip below", icon="ℹ️")

            ec1, ec2, _ = st.columns([3, 2, 2])
            send_email_clicked = ec1.button("✉️ Send Notification", type="primary",
                                            width="stretch", key="confirm_send_email")
            skip_email_clicked = ec2.button("Skip", type="secondary",
                                            width="stretch", key="confirm_skip_email")

            if send_email_clicked or skip_email_clicked:
                # Dismiss panel FIRST — prevents ghost re-render if downstream calls fail
                _tid_to_resume = (_ep or {}).get("tid", st.session_state.thread_id)
                st.session_state.email_pending    = None
                st.session_state.waiting_for_user = False
                config = {"configurable": {"thread_id": _tid_to_resume}}

                if skip_email_clicked:
                    noc_app.update_state(config, {"skip_email": True})
                    st.toast("Skipped — GLPI ticket still created.", icon="⏭️")
                else:
                    st.toast("Sending notification...", icon="📧")

                try:
                    noc_app.invoke(None, config=config)
                except Exception as _remedy_err:
                    st.toast(f"⚠️ Remedy error (ticket still saved): {_remedy_err}", icon="⚠️")

                # Auto-generate PIR for Critical / High tickets
                pir_path = ""
                if _snap_sev.upper() in ("CRITICAL", "HIGH"):
                    try:
                        _final_state   = noc_app.get_state(config).values
                        _elapsed_secs  = int(time.time() - st.session_state.sla_start_time) \
                                         if st.session_state.sla_start_time else 0
                        _sla_limit     = SLA_THRESHOLDS.get(_snap_sev.upper(), 3600)
                        pir_path = generate_pir_doc({
                            "ticket_id":          _snap_tid,
                            "category":           _snap_cat,
                            "severity":           _snap_sev,
                            "description":        _final_state.get("description", ""),
                            "analysis":           _final_state.get("analysis", ""),
                            "recommendation":     _final_state.get("recommendation", ""),
                            "runbook_match":      _final_state.get("runbook_match", ""),
                            "supervisor_reason":  _final_state.get("supervisor_reason", ""),
                            "glpi_ticket_id":     _final_state.get("glpi_ticket_id", ""),
                            "team":               _snap_team.get("team", ""),
                            "affected_node":      _snap_node,
                            "response_time_secs": _elapsed_secs,
                            "sla_breached":       _elapsed_secs > _sla_limit,
                            "correlated_with":    correlated_with if is_correlated else "",
                            "confidence_score":   confidence,
                            "opened_at":          datetime.fromtimestamp(
                                                      st.session_state.sla_start_time
                                                  ).strftime("%d %B %Y  %H:%M")
                                                  if st.session_state.sla_start_time else "",
                            "resolved_at":        datetime.now().strftime("%d %B %Y  %H:%M"),
                        })
                        st.toast(f"📄 PIR saved for {_snap_tid}", icon="📄")
                    except Exception as _pir_err:
                        st.toast(f"⚠️ PIR generation failed: {_pir_err}", icon="⚠️")

                save_and_advance(
                    session_state=st.session_state, severity=_snap_sev,
                    correlated_with=correlated_with, is_correlated=is_correlated,
                    confidence=confidence, status=status_to_save,
                    pir_path=pir_path,
                )

                # Trend analysis — check for patterns in recently resolved tickets
                try:
                    _trend = check_trends(st.session_state.processed_tickets)
                    if _trend:
                        st.session_state.trend_insight = _trend
                except Exception:
                    pass

                try:
                    analyze_current_ticket()
                except Exception:
                    pass
                st.rerun()

    # ── Pending queue (shown when no ticket is at HITL) ───────────────────────
    SEV_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}

    if not st.session_state.waiting_for_user:
        pending = get_pending_tickets()
        if pending:
            all_count  = len(pending)
            crit_count = sum(1 for t in pending if t.get("Severity") == "Critical")
            high_count = sum(1 for t in pending if t.get("Severity") == "High")
            med_count  = sum(1 for t in pending if t.get("Severity") == "Medium")
            low_count  = sum(1 for t in pending if t.get("Severity") == "Low")

            filter_col, queue_col = st.columns([1, 5])

            with filter_col:
                st.markdown("**Filter**")
                st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
                for label, key, count in [
                    ("All",        "All",      all_count),
                    ("🔴 Critical", "Critical", crit_count),
                    ("🟠 High",     "High",     high_count),
                    ("🟡 Medium",   "Medium",   med_count),
                    ("🟢 Low",      "Low",      low_count),
                ]:
                    if st.button(
                        f"{label}  {count}",
                        key=f"filter_{key}",
                        width="stretch",
                        type="primary" if st.session_state.queue_filter == key else "secondary",
                    ):
                        st.session_state.queue_filter = key
                        st.rerun()

            with queue_col:
                filtered = (
                    pending if st.session_state.queue_filter == "All"
                    else [t for t in pending if t.get("Severity") == st.session_state.queue_filter]
                )
                active = st.session_state.queue_filter
                st.markdown(f"#### 📋 {'All Alerts' if active == 'All' else active + ' Alerts'} — **{len(filtered)}** tickets")

                # Header row
                h = st.columns([1.1, 1.2, 1.1, 3.5, 1.6, 0.8])
                for col, lbl in zip(h, ["Severity", "Ticket ID", "Category", "Alert Message", "Node", ""]):
                    col.markdown(
                        f"<p style='font-size:11px;font-weight:700;color:#6b7280;"
                        f"text-transform:uppercase;margin:0;padding-bottom:2px;'>{lbl}</p>",
                        unsafe_allow_html=True,
                    )
                st.markdown("<hr style='margin:2px 0 4px 0;border-color:#e5e7eb;'>", unsafe_allow_html=True)

                for t in filtered:
                    tid      = t.get("Ticket_ID", "")
                    cat      = t.get("Category",  "Unknown")
                    sev      = t.get("Severity",  "Medium")
                    msg      = t.get("Alert_Message", "")
                    node     = str(t.get("Affected_Node", "—"))
                    cat_icon = CATEGORY_ICONS.get(cat, "📋")
                    sev_icon = SEV_ICON.get(sev, "⚪")

                    c0, c1, c2, c3, c4, c5 = st.columns([1.1, 1.2, 1.1, 3.5, 1.6, 0.8])
                    c0.markdown(f"**{sev_icon} {sev}**")
                    c1.code(tid, language=None)
                    c2.markdown(f"{cat_icon} {cat}")
                    c3.markdown(f"{msg[:95]}{'…' if len(msg) > 95 else ''}")
                    c4.caption(node[:28])
                    if c5.button("▶", key=f"proc_{tid}", help=f"Process {tid}", type="primary"):
                        analyze_current_ticket(specific_ticket=t)
                        st.rerun()

                    st.markdown("<hr style='margin:3px 0;border-color:#f3f4f6;'>", unsafe_allow_html=True)
        else:
            st.success("🎉 All tickets processed — queue is clear!")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYTICS DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("📈 NOC/SOC Performance Metrics")

    if not st.session_state.processed_tickets:
        st.info("No data yet. Process some tickets in the Operations Center to see metrics here.")
    else:
        metrics_df = pd.DataFrame(st.session_state.processed_tickets)
        sla_breached_count = int(metrics_df["SLA_Breached"].sum()) if "SLA_Breached" in metrics_df.columns else 0
        approved_count_m   = len(metrics_df[metrics_df["Status"].isin(["Approved", "Approved (Queue)"])])
        rejected_count_m   = len(metrics_df[metrics_df["Status"] == "Rejected"])
        duplicate_count_m  = len(metrics_df[metrics_df["Status"] == "Dropped (Duplicate)"])

        # KPI row
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Processed",    len(metrics_df))
        m2.metric("Approved ✅",         approved_count_m)
        m3.metric("Rejected ❌",         rejected_count_m)
        m4.metric("Duplicates 🗑️",      duplicate_count_m)
        m5.metric("SLA Breached 🚨",     sla_breached_count)
        if "Confidence_Score" in metrics_df.columns:
            scores   = pd.to_numeric(metrics_df["Confidence_Score"], errors="coerce").dropna()
            avg_conf = int(scores.mean()) if not scores.empty else 0
        else:
            avg_conf = 0
        m6.metric("Avg Confidence 🎯",  f"{avg_conf}%")

        st.divider()

        # Charts row 1 — category pie + severity bar
        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("**Tickets by Category**")
            cat_counts = metrics_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig = px.pie(cat_counts, names="Category", values="Count",
                         color_discrete_sequence=px.colors.qualitative.Set2, hole=0.4)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), showlegend=False, height=300)
            st.plotly_chart(fig, width="stretch")

        with ch2:
            st.markdown("**Tickets by Severity**")
            sev_order  = ["Critical", "High", "Medium", "Low"]
            sev_colors = {"Critical":"#d62728","High":"#ff7f0e","Medium":"#f0c419","Low":"#2ca02c"}
            sev_counts = metrics_df["Severity"].value_counts().reindex(sev_order).dropna().reset_index()
            sev_counts.columns = ["Severity", "Count"]
            fig = px.bar(sev_counts, x="Severity", y="Count", color="Severity",
                         color_discrete_map=sev_colors, text="Count")
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False, margin=dict(t=10,b=10,l=10,r=10),
                              height=300, xaxis_title="", yaxis_title="Count")
            st.plotly_chart(fig, width="stretch")

        # Charts row 2 — timeline + status by category
        ch3, ch4 = st.columns(2)
        with ch3:
            st.markdown("**Ticket Volume Over Time**")
            if "Timestamp" in metrics_df.columns:
                time_df = metrics_df.copy()
                time_df["Timestamp"] = pd.to_datetime(time_df["Timestamp"], errors="coerce")
                time_df = time_df.dropna(subset=["Timestamp"])
                time_df["Hour"] = time_df["Timestamp"].dt.floor("H")
                vol = time_df.groupby("Hour").size().reset_index(name="Count")
                fig = px.line(vol, x="Hour", y="Count", markers=True, line_shape="spline",
                              color_discrete_sequence=["#636efa"])
                fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300,
                                  xaxis_title="Time", yaxis_title="Tickets")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No timestamp data available.")

        with ch4:
            st.markdown("**Status Breakdown by Category**")
            if "Category" in metrics_df.columns and "Status" in metrics_df.columns:
                grp = metrics_df.groupby(["Category", "Status"]).size().reset_index(name="Count")
                fig = px.bar(grp, x="Category", y="Count", color="Status",
                             color_discrete_sequence=px.colors.qualitative.Pastel,
                             barmode="stack", text="Count")
                fig.update_traces(textposition="inside")
                fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300,
                                  xaxis_title="", yaxis_title="Count", legend_title="Status")
                st.plotly_chart(fig, width="stretch")

        # Charts row 3 — confidence histogram + SLA by severity
        ch5, ch6 = st.columns(2)
        with ch5:
            st.markdown("**AI Confidence Score Distribution**")
            if "Confidence_Score" in metrics_df.columns:
                conf_df = metrics_df.copy()
                conf_df["Confidence_Score"] = pd.to_numeric(conf_df["Confidence_Score"], errors="coerce")
                if not conf_df["Confidence_Score"].dropna().empty:
                    fig = px.histogram(conf_df.dropna(subset=["Confidence_Score"]),
                                       x="Confidence_Score", nbins=10,
                                       color_discrete_sequence=["#00cc96"], range_x=[0, 100])
                    fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300,
                                      xaxis_title="Confidence Score (%)", yaxis_title="Tickets", bargap=0.1)
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("No confidence scores recorded yet.")

        with ch6:
            st.markdown("**SLA Status by Severity**")
            if "SLA_Breached" in metrics_df.columns and "Severity" in metrics_df.columns:
                sla_df = metrics_df.copy()
                sla_df["SLA_Status"] = sla_df["SLA_Breached"].apply(
                    lambda x: "Breached 🔴" if x else "Within SLA 🟢"
                )
                sla_grp = sla_df.groupby(["Severity", "SLA_Status"]).size().reset_index(name="Count")
                fig = px.bar(sla_grp, x="Severity", y="Count", color="SLA_Status",
                             color_discrete_map={"Breached 🔴": "#d62728", "Within SLA 🟢": "#2ca02c"},
                             barmode="group", text="Count",
                             category_orders={"Severity": sev_order})
                fig.update_traces(textposition="outside")
                fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=300,
                                  xaxis_title="", yaxis_title="Count", legend_title="SLA")
                st.plotly_chart(fig, width="stretch")

        # Detailed audit log with filters
        st.divider()
        st.markdown("**📋 Detailed Audit Log**")
        fc1, fc2, fc3 = st.columns(3)
        f_cat    = fc1.multiselect("Filter by Category", options=metrics_df["Category"].unique().tolist(), default=[])
        f_sev    = fc2.multiselect("Filter by Severity", options=["Critical","High","Medium","Low"],       default=[])
        f_status = fc3.multiselect("Filter by Status",   options=metrics_df["Status"].unique().tolist(),   default=[])

        filtered_df = metrics_df.copy()
        if f_cat:    filtered_df = filtered_df[filtered_df["Category"].isin(f_cat)]
        if f_sev:    filtered_df = filtered_df[filtered_df["Severity"].isin(f_sev)]
        if f_status: filtered_df = filtered_df[filtered_df["Status"].isin(f_status)]

        st.caption(f"Showing {len(filtered_df)} of {len(metrics_df)} tickets")
        st.dataframe(filtered_df, width="stretch", height=350)

        st.divider()

        # Post-Incident Reports
        pir_tickets = [
            t for t in st.session_state.processed_tickets
            if t.get("PIR_Path") and os.path.isfile(t["PIR_Path"])
        ]
        if pir_tickets:
            st.subheader("📄 Post-Incident Reports")
            st.caption("Auto-generated for Critical and High severity tickets")
            _SEV_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
            for _pt in pir_tickets:
                _pc1, _pc2, _pc3, _pc4 = st.columns([1.2, 1.3, 1.0, 1.5])
                _pc1.code(_pt["Ticket_ID"], language=None)
                _pc2.markdown(
                    f"{CATEGORY_ICONS.get(_pt.get('Category',''), '📋')} "
                    f"{_pt.get('Category','')}"
                )
                _psev = _pt.get("Severity", "")
                _pc3.markdown(f"{_SEV_ICON.get(_psev,'⚪')} **{_psev}**")
                with open(_pt["PIR_Path"], "rb") as _pf:
                    _pc4.download_button(
                        label     = "📥 Download PIR",
                        data      = _pf.read(),
                        file_name = f"{_pt['Ticket_ID']}_PIR.docx",
                        mime      = "application/vnd.openxmlformats-officedocument"
                                    ".wordprocessingml.document",
                        key       = f"pir_dl_{_pt['Ticket_ID']}",
                    )
            st.divider()

        # Shift Handoff Report
        st.subheader("📋 Shift Handoff Report")
        hf1, hf2, hf3, hf4 = st.columns([2, 2, 2, 2])
        outgoing_eng = hf1.text_input("Outgoing Engineer", placeholder="e.g. Ahmed Al-Rashidi")
        incoming_eng = hf2.text_input("Incoming Engineer", placeholder="e.g. Sara Khalil")
        shift_period = hf3.text_input("Shift Period",       placeholder="e.g. 08:00 – 16:00")
        report_mode  = hf4.radio(
            "Report Mode",
            options=["Quick (1 page)", "Full (7 sections)"],
            index=0,
            help="Quick: Open items + metrics + watch list.  Full: all 7 sections with AI narratives.",
            horizontal=True,
        )
        short_mode = report_mode == "Quick (1 page)"
        st.caption("**Quick** — ~1 page essentials only.  **Full** — complete report with AI narratives and full incident log.")

        gen_col, dl_col, excel_col, _ = st.columns([1.4, 1.4, 1.4, 1.8])

        with gen_col:
            if st.button("🔄 Generate Handoff Report", type="primary", width="stretch"):
                with st.spinner("AI is writing the report… (~15 seconds)"):
                    try:
                        pending    = get_pending_tickets()
                        ai_content = run_handoff_llm(st.session_state.processed_tickets, pending)
                        buf = generate_handoff_report_doc(
                            tickets_data=st.session_state.processed_tickets,
                            pending_tickets=pending,
                            outgoing_eng=outgoing_eng,
                            incoming_eng=incoming_eng,
                            shift_period=shift_period,
                            ai_content=ai_content,
                            short_mode=short_mode,
                        )
                        st.session_state.handoff_doc_buf = buf.getvalue()
                        st.session_state.handoff_ready   = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Report generation failed: {e}")

        with dl_col:
            if st.session_state.handoff_ready and st.session_state.handoff_doc_buf:
                st.download_button(
                    label     = "📄 Download Handoff (.docx)",
                    data      = st.session_state.handoff_doc_buf,
                    file_name = f"NOC_Handoff_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime      = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    width     = "stretch",
                )
            else:
                st.button("📄 Download Handoff (.docx)", disabled=True, width="stretch")

        with excel_col:
            _cur_len = len(st.session_state.processed_tickets)
            if st.session_state.excel_report_len != _cur_len:
                st.session_state.excel_report_cache = generate_excel_report(
                    st.session_state.processed_tickets
                ).getvalue()
                st.session_state.excel_report_len = _cur_len
            st.download_button(
                label     = "📊 Download Excel Log (.xlsx)",
                data      = st.session_state.excel_report_cache,
                file_name = f"NOC_Audit_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width     = "stretch",
            )

        if st.session_state.handoff_ready:
            st.success("✅ Report ready — click **Download Handoff (.docx)** to save it.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — NOC AI CHATBOT
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    render_chatbot_tab(get_pending_fn=get_pending_tickets)


# ═════════════════════════════════════════════════════════════════════════════
# SLA TIMER — 1-second rerun tick (only fires while HITL panel is active)
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.waiting_for_user:
    time.sleep(1)
    st.rerun()
