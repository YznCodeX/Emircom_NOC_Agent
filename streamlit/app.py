import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import json
import os
import time
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from src.agent_graph import app, _glpi_create_ticket

PROCESSED_TICKETS_PATH = "data/processed_tickets.json"
SESSION_STATE_PATH = "data/session_state.json"

def load_processed_tickets():
    if os.path.exists(PROCESSED_TICKETS_PATH):
        with open(PROCESSED_TICKETS_PATH, "r") as f:
            tickets = json.load(f)
        # Ensure Confidence_Score is always str (old records may have int)
        for t in tickets:
            t["Confidence_Score"] = str(t.get("Confidence_Score") or "")
        return tickets
    return []

def save_processed_tickets(tickets):
    with open(PROCESSED_TICKETS_PATH, "w") as f:
        json.dump(tickets, f, indent=2)

def load_ticket_index():
    if os.path.exists(SESSION_STATE_PATH):
        with open(SESSION_STATE_PATH, "r") as f:
            return json.load(f).get("ticket_index", 0)
    return 0

def save_ticket_index(index):
    with open(SESSION_STATE_PATH, "w") as f:
        json.dump({"ticket_index": index}, f)

# --- Session State ---
if "ticket_index" not in st.session_state:
    st.session_state.ticket_index = load_ticket_index()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = ""
if "waiting_for_user" not in st.session_state:
    st.session_state.waiting_for_user = False
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""
if "current_node" not in st.session_state:
    st.session_state.current_node = "Idle 💤"
if "is_scanning" not in st.session_state:
    st.session_state.is_scanning = False
if "processed_tickets" not in st.session_state:
    st.session_state.processed_tickets = load_processed_tickets()
if "original_category" not in st.session_state:
    st.session_state.original_category = ""
if "sla_start_time" not in st.session_state:
    st.session_state.sla_start_time = None
if "auto_scan_enabled" not in st.session_state:
    st.session_state.auto_scan_enabled = False
if "last_auto_scan" not in st.session_state:
    st.session_state.last_auto_scan = 0.0
if "last_checked_display" not in st.session_state:
    st.session_state.last_checked_display = "Never"
if "confidence_score" not in st.session_state:
    st.session_state.confidence_score = None
if "confidence_reason" not in st.session_state:
    st.session_state.confidence_reason = ""
if "queue_scan_results" not in st.session_state:
    st.session_state.queue_scan_results = []
if "queue_filter" not in st.session_state:
    st.session_state.queue_filter = "All"
if "handoff_doc_buf" not in st.session_state:
    st.session_state.handoff_doc_buf = None
if "handoff_ready" not in st.session_state:
    st.session_state.handoff_ready = False

AUTO_SCAN_INTERVAL = 30

SLA_THRESHOLDS = {
    "CRITICAL": 15 * 60,
    "HIGH":     60 * 60,
    "MEDIUM":   4 * 60 * 60,
    "LOW":      24 * 60 * 60
}

CATEGORY_ICONS = {
    "Network":     "🌐",
    "Security":    "🔒",
    "Hardware":    "🖥️",
    "Cloud":       "☁️",
    "Application": "📱",
}

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🟢",
}

TEAM_ROUTING = {
    "Network":     {"team": "Network Operations Team",    "lead": "Sr. Network Engineer",    "email": "network-ops@emircom.com"},
    "Security":    {"team": "Security Operations (SOC)",  "lead": "Sr. SOC Analyst",         "email": "soc-team@emircom.com"},
    "Hardware":    {"team": "Field Engineering Team",     "lead": "Sr. Field Engineer",       "email": "field-eng@emircom.com"},
    "Cloud":       {"team": "Cloud Infrastructure Team",  "lead": "Sr. Cloud Engineer",       "email": "cloud-ops@emircom.com"},
    "Application": {"team": "Application Support Team",   "lead": "Sr. App Support Engineer", "email": "app-support@emircom.com"},
}

# ─── Report Generators ───────────────────────────────────────────────────────
def _set_cell_bg(cell, hex_color: str):
    """Apply a solid background fill colour to a Word table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tc_pr.append(shd)


def run_handoff_llm(tickets_data: list, pending_tickets: list) -> dict:
    """Single LLM call that writes the three narrative sections of the handoff report."""
    from src.agent_graph import llm

    processed_summary = json.dumps(tickets_data, indent=2)
    pending_summary   = json.dumps([
        {"Ticket_ID": t["Ticket_ID"], "Category": t["Category"],
         "Alert_Message": t.get("Alert_Message", "")}
        for t in pending_tickets
    ], indent=2)
    critical_ids = [t["Ticket_ID"] for t in tickets_data
                    if str(t.get("Severity", "")).upper() == "CRITICAL"]

    prompt = f"""You are a senior NOC Shift Lead at Emircom writing a formal end-of-shift handover report.

PROCESSED TICKETS THIS SHIFT:
{processed_summary}

PENDING (NOT YET PROCESSED) TICKETS:
{pending_summary}

CRITICAL TICKET IDs: {critical_ids}

Generate three sections. Reply ONLY with valid JSON — no markdown, no explanation:

{{
  "shift_narrative": "3-5 sentences. Cover: overall ticket volume, dominant categories, major patterns or correlations observed, SLA performance, and an overall severity assessment of the shift. Technical, direct, no filler.",
  "critical_summaries": {{
    "INC-XXXX": "2-3 sentences per critical ticket: what happened, what action was taken, current resolution status. Reference actual ticket data. If there are no critical tickets return an empty object {{}}"
  }},
  "watch_list": "3-5 sentences. Tell the incoming engineer specifically what to monitor: which devices, services, or alert patterns from this shift may re-occur or escalate. Reference actual ticket IDs, device names, or category trends from the data."
}}"""

    response = llm.invoke(prompt)
    raw = response.content.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def _styled_heading(doc, text: str, level: int = 1):
    """Add a heading with consistent dark-blue colour."""
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    return h


def _add_table(doc, headers: list, rows: list, col_widths: list | None = None):
    """Helper: dark-blue header row + alternating white/light rows."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"

    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        run = hdr[i].paragraphs[0].runs[0]
        run.bold           = True
        run.font.size      = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _set_cell_bg(hdr[i], "1F4E79")

    light_fill = "EBF3FB"
    for idx, row_data in enumerate(rows):
        cells = table.add_row().cells
        for j, val in enumerate(row_data):
            cells[j].text = str(val)
            for para in cells[j].paragraphs:
                for r in para.runs:
                    r.font.size = Pt(9)
            if idx % 2 == 1:
                _set_cell_bg(cells[j], light_fill)

    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)

    return table


def generate_handoff_report_doc(
    tickets_data:    list,
    pending_tickets: list,
    outgoing_eng:    str,
    incoming_eng:    str,
    shift_period:    str,
    ai_content:      dict,
    short_mode:      bool = False,
) -> io.BytesIO:
    """Build the full NOC Shift Handoff .docx and return as a BytesIO buffer."""

    doc = Document()

    # ── Page margins ─────────────────────────────────────────────────────────
    for sec in doc.sections:
        sec.top_margin    = Inches(0.9)
        sec.bottom_margin = Inches(0.9)
        sec.left_margin   = Inches(1.1)
        sec.right_margin  = Inches(1.1)

    sev_colors = {
        "CRITICAL": "C00000",
        "HIGH":     "C55A11",
        "MEDIUM":   "7F6000",
        "LOW":      "375623",
    }
    sev_fills = {
        "CRITICAL": "FF0000",
        "HIGH":     "FF8C00",
        "MEDIUM":   "FFC000",
        "LOW":      "70AD47",
    }

    # ════════════════════════════════════════════════════════════════════════
    # COVER BLOCK
    # ════════════════════════════════════════════════════════════════════════
    def _cp(text, size=11, bold=False, italic=False,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            rgb: RGBColor | None = None):
        p = doc.add_paragraph()
        p.alignment = align
        run = p.add_run(text)
        run.bold       = bold
        run.italic     = italic
        run.font.size  = Pt(size)
        if rgb:
            run.font.color.rgb = rgb
        return p

    _cp("EMIRCOM NOC / SOC COMMAND CENTER", size=18, bold=True,
        rgb=RGBColor(0x1F, 0x4E, 0x79))
    _cp("SHIFT HANDOFF REPORT", size=13, bold=True,
        rgb=RGBColor(0x2E, 0x74, 0xB5))
    _cp("Confidential — Internal Use Only", size=9, italic=True,
        rgb=RGBColor(0x80, 0x80, 0x80))
    doc.add_paragraph()

    # Shift info table (2-col, no outer border)
    info_table = doc.add_table(rows=5, cols=2)
    info_data = [
        ("Shift Date",        datetime.now().strftime("%d %B %Y")),
        ("Shift Period",      shift_period or "—"),
        ("Outgoing Engineer", outgoing_eng or "—"),
        ("Incoming Engineer", incoming_eng or "—"),
        ("Report Generated",  datetime.now().strftime("%H:%M")),
    ]
    for i, (label, value) in enumerate(info_data):
        lbl_cell = info_table.rows[i].cells[0]
        val_cell = info_table.rows[i].cells[1]
        lbl_cell.text = label
        val_cell.text = value
        lbl_run = lbl_cell.paragraphs[0].runs[0]
        lbl_run.bold = True
        lbl_run.font.size = Pt(10)
        lbl_run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        val_cell.paragraphs[0].runs[0].font.size = Pt(10)
    doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 1 — SHIFT NARRATIVE  (full mode only)
    # ════════════════════════════════════════════════════════════════════════
    if not short_mode:
        _styled_heading(doc, "1.  Shift Narrative")
        narrative = ai_content.get("shift_narrative", "No narrative generated.")
        p = doc.add_paragraph(narrative)
        p.runs[0].font.size = Pt(10.5)
        doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 2 — KEY METRICS
    # ════════════════════════════════════════════════════════════════════════
    _styled_heading(doc, "1.  Key Metrics" if short_mode else "2.  Key Metrics")

    total        = len(tickets_data)
    approved     = sum(1 for t in tickets_data if t["Status"] in ("Approved", "Approved (Queue)"))
    dropped      = sum(1 for t in tickets_data if t["Status"] == "Dropped (Duplicate)")
    rejected     = sum(1 for t in tickets_data if t["Status"] == "Rejected")
    sla_breached = sum(1 for t in tickets_data if t.get("SLA_Breached", False))
    crit_cnt     = sum(1 for t in tickets_data if str(t.get("Severity","")).upper() == "CRITICAL")
    high_cnt     = sum(1 for t in tickets_data if str(t.get("Severity","")).upper() == "HIGH")
    pending_cnt  = len(pending_tickets)

    metrics_headers = ["Metric", "Count"]
    metrics_rows    = [
        ("Total Tickets Processed",  total),
        ("Approved & Escalated",     approved),
        ("Duplicates Dropped",       dropped),
        ("Rejected",                 rejected),
        ("SLA Breaches",             sla_breached),
        ("Critical Incidents",       crit_cnt),
        ("High-Severity Incidents",  high_cnt),
        ("Pending (Not Processed)",  pending_cnt),
    ]
    _add_table(doc, metrics_headers, metrics_rows, col_widths=[3.0, 1.0])
    doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 3 — OPEN / PENDING ITEMS
    # ════════════════════════════════════════════════════════════════════════
    _styled_heading(doc, "2.  Open Items — Requires Incoming Engineer Attention"
                         if short_mode else "3.  Open Items — Requires Incoming Engineer Attention")

    if not pending_tickets:
        p = doc.add_paragraph("✅  Queue is clear. No open items for the incoming shift.")
        p.runs[0].font.size = Pt(10.5)
        p.runs[0].font.color.rgb = RGBColor(0x37, 0x56, 0x23)
    else:
        warn = doc.add_paragraph(
            f"⚠️  {len(pending_tickets)} ticket(s) were NOT processed this shift "
            "and must be handled immediately by the incoming engineer."
        )
        warn.runs[0].bold = True
        warn.runs[0].font.size = Pt(10.5)
        warn.runs[0].font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
        doc.add_paragraph()
        pending_headers = ["Ticket ID", "Category", "Alert / Description"]
        pending_rows = [
            (t["Ticket_ID"], t["Category"], t.get("Alert_Message", "")[:80])
            for t in pending_tickets
        ]
        _add_table(doc, pending_headers, pending_rows, col_widths=[1.2, 1.2, 4.6])

    doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # SECTIONS 4-6 — FULL MODE ONLY
    # ════════════════════════════════════════════════════════════════════════
    if not short_mode:

        # ── Section 4: Critical Incident Summaries (AI-written) ──────────────
        _styled_heading(doc, "4.  Critical Incident Summaries")

        critical_summaries: dict = ai_content.get("critical_summaries", {})
        critical_tickets = [t for t in tickets_data
                            if str(t.get("Severity","")).upper() == "CRITICAL"]

        if not critical_tickets:
            p = doc.add_paragraph("No Critical incidents recorded this shift.")
            p.runs[0].font.size = Pt(10.5)
        else:
            for t in critical_tickets:
                tid = t.get("Ticket_ID", "")
                h2  = doc.add_heading("", level=2)
                run = h2.add_run(
                    f"{tid}  —  {t.get('Category','')}  |  Status: {t.get('Status','')}"
                )
                run.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

                summary_text = critical_summaries.get(tid, "No AI summary available.")
                p = doc.add_paragraph(summary_text)
                p.runs[0].font.size = Pt(10.5)

                if t.get("Correlated_With"):
                    cn = doc.add_paragraph(f"↳  Correlated with: {t['Correlated_With']}")
                    cn.runs[0].font.size  = Pt(9.5)
                    cn.runs[0].italic     = True
                    cn.runs[0].font.color.rgb = RGBColor(0x40, 0x40, 0x80)
                doc.add_paragraph()

        # ── Section 5: Correlated Incident Groups ────────────────────────────
        _styled_heading(doc, "5.  Correlated Incident Groups")

        corr_groups: dict = {}
        for t in tickets_data:
            cw = t.get("Correlated_With", "")
            if cw:
                corr_groups.setdefault(cw, set()).add(cw)
                corr_groups[cw].add(t["Ticket_ID"])

        if not corr_groups:
            p = doc.add_paragraph("No correlated incident groups detected this shift.")
            p.runs[0].font.size = Pt(10.5)
        else:
            for group_label, (root, members) in enumerate(corr_groups.items(), start=1):
                gh = doc.add_paragraph()
                gr = gh.add_run(f"Group {group_label}  —  Root: {root}")
                gr.bold = True
                gr.font.size = Pt(10.5)
                gr.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
                mp = doc.add_paragraph(f"Linked tickets: {',  '.join(sorted(members))}")
                mp.runs[0].font.size = Pt(10)
                mp.runs[0].italic    = True
                doc.add_paragraph()

        # ── Section 6: Full Incident Log ─────────────────────────────────────
        _styled_heading(doc, "6.  Full Incident Log")

        log_headers = ["Ticket ID", "Category", "Severity", "Status",
                       "Response Time", "SLA Breached", "Correlated With", "Confidence"]
        log_table = doc.add_table(rows=1, cols=len(log_headers))
        log_table.style = "Light Grid Accent 1"

        hdr_cells = log_table.rows[0].cells
        for i, h in enumerate(log_headers):
            hdr_cells[i].text = h
            run = hdr_cells[i].paragraphs[0].runs[0]
            run.bold = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _set_cell_bg(hdr_cells[i], "1F4E79")

        light = "EBF3FB"
        for idx, t in enumerate(tickets_data):
            rt_secs  = int(t.get("Response_Time_Secs", 0) or 0)
            rt_str   = f"{rt_secs // 60}m {rt_secs % 60}s" if rt_secs else "—"
            severity = str(t.get("Severity", "")).upper()
            cells = log_table.add_row().cells
            cells[0].text = str(t.get("Ticket_ID",       ""))
            cells[1].text = str(t.get("Category",         ""))
            cells[2].text = severity
            cells[3].text = str(t.get("Status",           ""))
            cells[4].text = rt_str
            cells[5].text = "YES" if t.get("SLA_Breached", False) else "No"
            cells[6].text = str(t.get("Correlated_With",  "") or "—")
            cells[7].text = str(t.get("Confidence_Score", "") or "—")

            fill = sev_fills.get(severity, "CCCCCC")
            _set_cell_bg(cells[2], fill)
            runs = cells[2].paragraphs[0].runs
            if runs:
                runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                runs[0].bold = True
            if idx % 2 == 1:
                for j, cell in enumerate(cells):
                    if j != 2:
                        _set_cell_bg(cell, light)
            for cell in cells:
                for para in cell.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(9)

        doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 7 / 3 — WATCH LIST  (both modes, numbered accordingly)
    # ════════════════════════════════════════════════════════════════════════
    _styled_heading(doc, "3.  Watch List — Incoming Shift Priorities"
                         if short_mode else "7.  Watch List — Incoming Shift Priorities")

    watch = ai_content.get("watch_list", "No watch list generated.")
    p = doc.add_paragraph(watch)
    p.runs[0].font.size = Pt(10.5)
    doc.add_paragraph()

    # ════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════════════════
    sep = doc.add_paragraph("─" * 72)
    sep.alignment = WD_ALIGN_PARAGRAPH.CENTER

    foot = doc.add_paragraph(
        f"Generated by Emircom NOC AI Agent  •  {datetime.now().strftime('%d %B %Y  %H:%M')}  •  Confidential"
    )
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.runs[0].font.size  = Pt(8.5)
    foot.runs[0].italic     = True
    foot.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def generate_excel_report(tickets_data: list) -> io.BytesIO:
    """Build a styled .xlsx audit log and return it as a BytesIO buffer."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    buf = io.BytesIO()
    df_log = pd.DataFrame(tickets_data)

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:

        # ── Sheet 1: Audit Log ────────────────────────────────────────────────
        df_log.to_excel(writer, sheet_name="Audit Log", index=False)
        ws = writer.sheets["Audit Log"]

        # Header style
        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(bold=True, color="FFFFFF", size=10)
        for cell in ws[1]:
            cell.fill      = header_fill
            cell.font      = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Severity colour map
        sev_fills = {
            "CRITICAL": PatternFill("solid", fgColor="FF0000"),
            "HIGH":     PatternFill("solid", fgColor="FF8C00"),
            "MEDIUM":   PatternFill("solid", fgColor="FFC000"),
            "LOW":      PatternFill("solid", fgColor="70AD47"),
        }
        white_font = Font(bold=True, color="FFFFFF", size=10)

        # Find Severity column index
        headers = [c.value for c in ws[1]]
        sev_col_idx = headers.index("Severity") + 1 if "Severity" in headers else None

        thin = Side(style="thin", color="D9D9D9")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                cell.alignment = Alignment(vertical="center")
                cell.border    = border
                if sev_col_idx and cell.column == sev_col_idx:
                    sev_val = str(cell.value or "").upper()
                    fill    = sev_fills.get(sev_val)
                    if fill:
                        cell.fill = fill
                        cell.font = white_font

        # Auto-fit column widths (capped at 40)
        for col_idx, col_cells in enumerate(ws.columns, 1):
            max_len = max((len(str(c.value or "")) for c in col_cells), default=8)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 40)

        ws.row_dimensions[1].height = 20
        ws.freeze_panes = "A2"

        # ── Sheet 2: Summary ──────────────────────────────────────────────────
        total         = len(tickets_data)
        approved      = sum(1 for t in tickets_data if t["Status"] in ("Approved", "Approved (Queue)"))
        dropped       = sum(1 for t in tickets_data if t["Status"] == "Dropped (Duplicate)")
        rejected      = sum(1 for t in tickets_data if t["Status"] == "Rejected")
        sla_breached  = sum(1 for t in tickets_data if t.get("SLA_Breached", False))
        critical_cnt  = sum(1 for t in tickets_data if str(t.get("Severity","")).upper() == "CRITICAL")
        high_cnt      = sum(1 for t in tickets_data if str(t.get("Severity","")).upper() == "HIGH")

        cat_counts: dict = {}
        for t in tickets_data:
            c = t.get("Category", "Unknown")
            cat_counts[c] = cat_counts.get(c, 0) + 1

        summary_rows = [
            ("Metric", "Count"),
            ("Total Processed",      total),
            ("Approved & Escalated", approved),
            ("Duplicates Dropped",   dropped),
            ("Rejected",             rejected),
            ("SLA Breached",         sla_breached),
            ("Critical Incidents",   critical_cnt),
            ("High-Severity",        high_cnt),
            ("", ""),
            ("Category Breakdown",   ""),
        ] + [(cat, cnt) for cat, cnt in sorted(cat_counts.items())]

        df_summary = pd.DataFrame(summary_rows[1:], columns=summary_rows[0])
        df_summary.to_excel(writer, sheet_name="Summary", index=False)

        ws2 = writer.sheets["Summary"]
        for cell in ws2[1]:
            cell.fill      = header_fill
            cell.font      = header_font
            cell.alignment = Alignment(horizontal="center")
        for col_cells in ws2.columns:
            max_len = max((len(str(c.value or "")) for c in col_cells), default=8)
            ws2.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 35)

        # ── Sheet 3: By Category ─────────────────────────────────────────────
        if not df_log.empty and "Category" in df_log.columns:
            cat_df = df_log.groupby(["Category", "Status"]).size().unstack(fill_value=0).reset_index()
            cat_df.to_excel(writer, sheet_name="By Category", index=False)
            ws3 = writer.sheets["By Category"]
            for cell in ws3[1]:
                cell.fill = header_fill
                cell.font = header_font
            for col_cells in ws3.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=8)
                ws3.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 25)

    buf.seek(0)
    return buf


def get_sla_status(severity, start_time):
    limit = SLA_THRESHOLDS.get(severity.upper(), 60 * 60)
    elapsed = time.time() - start_time
    remaining = limit - elapsed
    pct_used = elapsed / limit
    return elapsed, remaining, pct_used

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Emircom NOC AI Agent", page_icon="🛡️", layout="wide")

# ─── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ NOC Command Center")
    st.caption(f"🕐 {datetime.now().strftime('%d %b %Y  %H:%M:%S')}")
    st.divider()

    st.markdown("#### ⚙️ Auto-Scan")
    auto_scan_toggle = st.toggle(
        "Enable Auto-Scan (every 30s)",
        value=st.session_state.auto_scan_enabled,
    )
    if auto_scan_toggle != st.session_state.auto_scan_enabled:
        st.session_state.auto_scan_enabled = auto_scan_toggle
        if auto_scan_toggle:
            st.session_state.last_auto_scan = 0.0

    if st.session_state.auto_scan_enabled:
        st.success("🟢 Auto-Scan: ACTIVE")
        st.caption(f"Last checked: {st.session_state.last_checked_display}")
    else:
        st.warning("🔴 Auto-Scan: OFF")

    st.divider()
    st.markdown("#### 📡 Data Source")
    data_source = st.radio(
        "Alert feed:",
        ["Mock CSV", "Cisco DNA Center", "Both"],
        index=0,
        help="Mock CSV = sample data  |  DNA Center = live Cisco sandbox  |  Both = combined"
    )
    if data_source in ("Cisco DNA Center", "Both"):
        if st.button("🔄 Refresh Live Data", use_container_width=True):
            st.session_state.pop("dnac_alerts_cache", None)

    st.divider()
    st.markdown("#### 📂 Current Node")
    st.info(st.session_state.current_node)
    st.divider()
    st.file_uploader("Upload Logs File (.csv, .txt)", type=["csv", "txt"])

# ─── Load Data ──────────────────────────────────────────────────────────────
def _load_dnac_alerts():
    """Fetch live alerts from Cisco DNA Center (cached in session state)."""
    if "dnac_alerts_cache" not in st.session_state:
        try:
            from cisco.devnet_connector import get_live_alerts
            alerts = get_live_alerts()
            # Ensure required columns exist
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
    mock_df = pd.DataFrame([{"Ticket_ID": "INC-1001", "Category": "Network",
                             "Alert_Message": "High CPU utilization", "Raw_Logs": "CPU at 99%"}])

if data_source == "Mock CSV":
    df = mock_df
elif data_source == "Cisco DNA Center":
    dnac_alerts = _load_dnac_alerts()
    if dnac_alerts:
        df = pd.DataFrame(dnac_alerts)
    else:
        st.info("No active alerts from DNA Center — all devices healthy.")
        df = pd.DataFrame(columns=mock_df.columns)
else:  # Both
    dnac_alerts = _load_dnac_alerts()
    dnac_df = pd.DataFrame(dnac_alerts) if dnac_alerts else pd.DataFrame(columns=mock_df.columns)
    df = pd.concat([mock_df, dnac_df], ignore_index=True).drop_duplicates(subset="Ticket_ID")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def get_processed_ids():
    return {t["Ticket_ID"] for t in st.session_state.processed_tickets}

def get_pending_tickets():
    processed = get_processed_ids()
    return df[~df["Ticket_ID"].isin(processed)].to_dict("records")

def batch_scan_queue():
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
4. Group: same letter (A, B, C...) for tickets sharing the same root cause. Use "—" if standalone.

PENDING TICKETS:
{ticket_list}

Reply ONLY with a valid JSON array, no markdown:
[{{"ticket_id":"...","severity":"...","alert_type":"...","summary":"...","group":"..."}}]"""

    response = llm.invoke(prompt)
    raw = response.content.replace("```json","").replace("```","").strip()
    return json.loads(raw)

# ─── Analyze Ticket ─────────────────────────────────────────────────────────
def analyze_current_ticket():
    # Skip tickets already processed via Queue View
    processed = get_processed_ids()
    while st.session_state.ticket_index < len(df):
        if df.iloc[st.session_state.ticket_index]["Ticket_ID"] not in processed:
            break
        st.session_state.ticket_index += 1
        save_ticket_index(st.session_state.ticket_index)

    if st.session_state.ticket_index >= len(df):
        st.session_state.is_scanning = False
        st.session_state.ticket_index = 0
        save_ticket_index(0)
        return

    ticket = df.iloc[st.session_state.ticket_index]
    st.session_state.thread_id = ticket["Ticket_ID"]
    st.session_state.original_category = ticket["Category"]
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    inputs = {
        "ticket_id":   ticket["Ticket_ID"],
        "category":    ticket["Category"],
        "description": ticket.get("Alert_Message", ""),
        "logs":        ticket.get("Raw_Logs", ""),
    }

    with st.spinner(f"🤖 Analyzing {ticket['Ticket_ID']}..."):
        app.invoke(inputs, config=config)
        state = app.get_state(config)

        if state.next and state.next[0] in ["remedy", "drop"]:
            st.session_state.waiting_for_user = True
            st.session_state.sla_start_time = time.time()
            action = "Ticket Creation" if state.next[0] == "remedy" else "DROP Duplicate"
            st.session_state.current_node = f"⏳ HITL: {action}"
            st.session_state.analysis_result = state.values.get("analysis", "")
            # Store confidence score directly from state at analysis time
            st.session_state.confidence_score = state.values.get("confidence_score", None)
            try:
                import re
                raw = st.session_state.analysis_result.replace("```json","").replace("```","").strip()
                try:
                    parsed_cr = json.loads(raw)
                except json.JSONDecodeError:
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    parsed_cr = json.loads(match.group()) if match else {}
                st.session_state.confidence_reason = parsed_cr.get("Confidence_Reason", "")
            except Exception:
                st.session_state.confidence_reason = ""

# ─── Page Header ────────────────────────────────────────────────────────────
st.title("🛡️ Emircom NOC & SOC Command Center")

tab1, tab2, tab3 = st.tabs(["🚀 Live Operations", "📡 Queue View", "📊 Analytics Dashboard"])

# ════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Live Stats Strip ────────────────────────────────────────────────────
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
    st.divider()

    # ── Idle State (no ticket waiting) ──────────────────────────────────────
    if not st.session_state.waiting_for_user:
        if st.session_state.ticket_index < len(df):

            # Mini ticket cards for next 3 in queue
            st.markdown("#### 📋 Upcoming Queue")
            preview = df.iloc[st.session_state.ticket_index : st.session_state.ticket_index + 3]
            card_cols = st.columns(max(len(preview), 1))
            for i, (_, t) in enumerate(preview.iterrows()):
                with card_cols[i]:
                    icon = CATEGORY_ICONS.get(t["Category"], "📋")
                    with st.container(border=True):
                        st.markdown(f"**{t['Ticket_ID']}**")
                        st.caption(f"{icon} {t['Category']}")
                        msg = t["Alert_Message"]
                        st.caption(msg[:70] + "…" if len(msg) > 70 else msg)

            st.divider()

            if st.session_state.auto_scan_enabled:
                time_since = time.time() - st.session_state.last_auto_scan
                secs_left  = max(0, int(AUTO_SCAN_INTERVAL - time_since))
                btn_col, info_col = st.columns([1, 3])
                with btn_col:
                    if st.button("🚀 Scan Now", type="primary", use_container_width=True):
                        st.session_state.is_scanning = True
                        st.session_state.last_auto_scan = time.time()
                        st.session_state.last_checked_display = datetime.now().strftime("%H:%M:%S")
                        analyze_current_ticket()
                        st.rerun()
                with info_col:
                    if secs_left > 0:
                        st.info(f"⏱️ Next auto-scan in **{secs_left}s**")
                    else:
                        st.info("⏱️ Auto-scan running…")
            else:
                if st.button("🚀 Start NOC Auto-Scan", type="primary"):
                    st.session_state.is_scanning = True
                    analyze_current_ticket()
                    st.rerun()
        else:
            st.success("🎉 All tickets in the queue have been processed!")

    # ── HITL Panel ──────────────────────────────────────────────────────────
    if st.session_state.waiting_for_user:

        # Parse analysis JSON — robust extractor handles extra text around JSON
        def _extract_json(raw: str) -> dict:
            """Try multiple strategies to extract a JSON object from LLM output."""
            # Strategy 1: clean markdown and parse directly
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
            # Strategy 2: find first { ... } block
            import re
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            # Strategy 3: give up, return empty dict
            return {}

        try:
            parsed        = _extract_json(st.session_state.analysis_result)
            severity      = parsed.get("Severity",            "Unknown")
            category      = parsed.get("Categorization",      "Unknown")
            affected_node = parsed.get("Affected_Node",        "N/A")
            root_cause    = parsed.get("Root_Cause",           "N/A")
            biz_impact    = parsed.get("Business_Impact",      "N/A")
            symptom       = parsed.get("Symptom_Description",  "N/A")
            rec_action    = parsed.get("Recommended_Action",   "Review logs")
            conf_reason   = parsed.get("Confidence_Reason",    "")
            is_drop       = "DROP ALERT" in rec_action
            if not parsed:
                raise ValueError("Empty JSON")
        except Exception:
            # Last resort — show raw output instead of a scary warning
            st.info("ℹ️ Showing raw agent output — could not extract structured fields.")
            severity = category = "Unknown"
            affected_node = root_cause = biz_impact = symptom = rec_action = "N/A"
            conf_reason = ""
            is_drop = False

        # State values
        config_check  = {"configurable": {"thread_id": st.session_state.thread_id}}
        agent_state   = app.get_state(config_check)
        is_correlated = agent_state.values.get("is_correlated", False)
        correlated_with = agent_state.values.get("correlated_with", "")
        # Primary: session state (set at analysis time)
        # Fallback: agent state (handles app restarts mid-ticket)
        confidence  = st.session_state.confidence_score
        conf_reason = st.session_state.confidence_reason
        if confidence is None:
            confidence = agent_state.values.get("confidence_score", None)
            if confidence is not None:
                try:
                    raw_fb = st.session_state.analysis_result.replace("```json","").replace("```","").strip()
                    conf_reason = json.loads(raw_fb).get("Confidence_Reason", "")
                except Exception:
                    conf_reason = ""

        team_info        = TEAM_ROUTING.get(st.session_state.original_category,
                           {"team": "NOC Tier-2", "lead": "NOC Shift Lead", "email": "noc-support@emircom.com"})
        remedy_ticket    = f"REM-{st.session_state.thread_id.replace('INC-', '')}-{datetime.now().strftime('%H%M')}"
        sev_icon         = SEVERITY_COLORS.get(severity.upper(), "⚪")
        cat_icon         = CATEGORY_ICONS.get(st.session_state.original_category, "📋")

        # ── Ticket Header Card ───────────────────────────────────────────────
        header = (f"{sev_icon} &nbsp; **{severity.upper()}** &nbsp;|&nbsp; "
                  f"`{st.session_state.thread_id}` &nbsp;|&nbsp; "
                  f"{cat_icon} {st.session_state.original_category} &nbsp;|&nbsp; "
                  f"📍 {affected_node}")

        if severity.upper() == "CRITICAL":
            st.error(header)
        elif severity.upper() == "HIGH":
            st.warning(header)
        elif severity.upper() == "MEDIUM":
            st.info(header)
        else:
            st.success(header)

        # ── Pipeline Steps ───────────────────────────────────────────────────
        st.markdown(
            "<div style='display:flex;justify-content:space-between;align-items:center;"
            "background:#f0f2f6;border-radius:8px;padding:8px 16px;font-size:13px;margin-bottom:4px'>"
            "<span>✅ Triage</span>"
            "<span style='color:#ccc'>──▶</span>"
            "<span>✅ Dedup</span>"
            "<span style='color:#ccc'>──▶</span>"
            "<span>✅ Analysis</span>"
            "<span style='color:#ccc'>──▶</span>"
            "<span>✅ Correlation</span>"
            "<span style='color:#ccc'>──▶</span>"
            "<span style='font-weight:bold;color:#d62728'>⏳ HITL</span>"
            "</div>",
            unsafe_allow_html=True
        )

        # Correlation alert
        if is_correlated and correlated_with:
            st.warning(f"🔗 **Root Cause Correlation** — Shares root cause with: **{correlated_with}** — Investigate as one incident before escalating separately.")

        # Dedup warning
        if "DEDUP_WARN" in rec_action or "DEDUP_ERROR" in rec_action:
            st.warning("⚠️ Deduplication engine failed — ticket passed through unverified. Manual duplicate check recommended.")

        st.divider()

        # ── 2-Column Split ───────────────────────────────────────────────────
        left_col, right_col = st.columns([6, 4])

        # LEFT: Tabbed analysis
        with left_col:
            tab_sum, tab_logs, tab_email = st.tabs(["📋 Summary", "📜 Raw Logs", "📧 Email Template"])

            with tab_sum:
                summary_df = pd.DataFrame({
                    "Field":   ["Categorization", "Affected Node", "Severity",
                                "Business Impact", "Symptom", "Root Cause", "Recommended Action"],
                    "Details": [category, affected_node, severity,
                                biz_impact, symptom, root_cause, rec_action],
                })
                st.dataframe(summary_df, hide_index=True, use_container_width=True, height=280)

            with tab_logs:
                raw_logs = "No logs available."
                if st.session_state.ticket_index < len(df):
                    raw_logs = df.iloc[st.session_state.ticket_index].get("Raw_Logs", "No logs available.")
                st.code(raw_logs, language=None)

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

        # RIGHT: Action panel
        with right_col:
            with st.container(border=True):

                # ── 1. Decision Buttons ───────────────────────────────────────
                if is_drop:
                    st.error("🛑 **DUPLICATE DETECTED**")
                    st.caption(rec_action)
                    btn_approve_label = "✅ Approve Drop"
                    status_to_save    = "Dropped (Duplicate)"
                else:
                    btn_approve_label = "✅ Approve & Escalate"
                    status_to_save    = "Approved"

                b1, b2 = st.columns(2)
                approve_clicked = b1.button(btn_approve_label, type="primary", use_container_width=True)
                reject_clicked  = b2.button("❌ Reject",                        use_container_width=True)

                st.divider()

                # ── 2. SLA Timer (compact, no heading) ───────────────────────
                if st.session_state.sla_start_time and severity.upper() not in ("UNKNOWN", ""):
                    elapsed, remaining, pct_used = get_sla_status(severity, st.session_state.sla_start_time)
                    sla_limit = SLA_THRESHOLDS.get(severity.upper(), 3600)
                    if remaining <= 0:
                        st.error("🚨 SLA BREACHED")
                    else:
                        mins_r = int(remaining // 60)
                        secs_r = int(remaining % 60)
                        mins_e = int(elapsed // 60)
                        secs_e = int(elapsed % 60)
                        sla_text = f"⏱️ SLA — {mins_r}m {secs_r}s left  (elapsed {mins_e}m {secs_e}s / {sla_limit // 60}m)"
                        if pct_used >= 0.75:
                            st.warning(f"⚠️ {mins_r}m {secs_r}s remaining", icon=None)
                        st.progress(min(pct_used, 1.0), text=sla_text)

                # ── 3. Confidence Score (compact, no heading) ─────────────────
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

                # ── 4. Remedy + Team (compact single block) ───────────────────
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
                        unsafe_allow_html=True
                    )

            # ── Handle button actions ────────────────────────────────────────
            def _save_and_advance(status):
                elapsed_secs = int(time.time() - st.session_state.sla_start_time) if st.session_state.sla_start_time else 0
                sla_limit    = SLA_THRESHOLDS.get(severity.upper(), 3600)
                st.session_state.processed_tickets.append({
                    "Ticket_ID":        st.session_state.thread_id,
                    "Category":         st.session_state.original_category,
                    "Severity":         severity,
                    "Status":           status,
                    "Response_Time_Secs": elapsed_secs,
                    "SLA_Breached":     elapsed_secs > sla_limit,
                    "Correlated_With":  correlated_with if is_correlated else "",
                    "Confidence_Score": str(confidence) if confidence is not None else "",
                })
                save_processed_tickets(st.session_state.processed_tickets)
                st.session_state.waiting_for_user = False
                st.session_state.current_node = "Idle 💤"
                st.session_state.confidence_score = None
                st.session_state.confidence_reason = ""
                st.session_state.ticket_index += 1
                save_ticket_index(st.session_state.ticket_index)

            if approve_clicked:
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                app.invoke(None, config=config)
                _save_and_advance(status_to_save)
                analyze_current_ticket()
                st.rerun()

            if reject_clicked:
                _save_and_advance("Rejected")
                analyze_current_ticket()
                st.rerun()

# ════════════════════════════════════════════════════════════════════════════
with tab2:  # Queue View

    SEV_ORDER  = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    SEV_ICONS  = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
    ALERT_ICONS = {
        "Device Down":    "📡",
        "Link Down":      "🔗",
        "Resource Down":  "📉",
        "Security Alert": "🔒",
        "Performance":    "📊",
        "Other":          "📋",
    }

    # ── Top bar ──────────────────────────────────────────────────────────────
    hd_col, btn_col = st.columns([5, 1])
    hd_col.markdown("### 📡 Queue Intelligence View")
    scan_clicked = btn_col.button("🔍 Scan Queue", type="primary", use_container_width=True)

    if scan_clicked:
        with st.spinner("🤖 AI scanning all pending tickets…"):
            try:
                st.session_state.queue_scan_results = batch_scan_queue()
                st.session_state.queue_filter = "All"
            except Exception as e:
                st.error(f"Scan failed: {e}")

    if not st.session_state.queue_scan_results:
        pending_count = len(get_pending_tickets())
        st.info(f"**{pending_count} tickets** waiting in queue. Click **🔍 Scan Queue** to let the AI triage and group them.")
    else:
        results = st.session_state.queue_scan_results

        # ── Severity counts ───────────────────────────────────────────────
        sev_counts = {"All": len(results)}
        for r in results:
            s = r.get("severity", "Low")
            sev_counts[s] = sev_counts.get(s, 0) + 1

        # ── Layout: left filter | right tickets ───────────────────────────
        f_col, t_col = st.columns([1, 5])

        with f_col:
            st.markdown("**Severity Filter**")
            for sev in ["All", "Critical", "High", "Medium", "Low"]:
                count = sev_counts.get(sev, 0)
                icon  = SEV_ICONS.get(sev, "📋")
                label = f"{icon} {sev}  ({count})" if sev != "All" else f"📋 All  ({count})"
                is_active = st.session_state.queue_filter == sev
                if st.button(label, use_container_width=True,
                             type="primary" if is_active else "secondary",
                             key=f"filter_{sev}"):
                    st.session_state.queue_filter = sev
                    st.rerun()

        with t_col:
            # Filter + sort
            filtered = results if st.session_state.queue_filter == "All" else [
                r for r in results if r.get("severity") == st.session_state.queue_filter
            ]
            filtered = sorted(filtered, key=lambda x: SEV_ORDER.get(x.get("severity","Low"), 3))

            if not filtered:
                st.info("No tickets match this filter.")
            else:
                # Build groups
                groups: dict = {}
                for r in filtered:
                    g = r.get("group", "—")
                    if g != "—":
                        groups.setdefault(g, []).append(r["ticket_id"])

                shown_group_banners = set()

                for r in filtered:
                    tid      = r.get("ticket_id", "")
                    severity = r.get("severity", "Unknown")
                    atype    = r.get("alert_type", "Other")
                    summary  = r.get("summary", "")
                    group    = r.get("group", "—")
                    sev_icon = SEV_ICONS.get(severity, "⚪")
                    a_icon   = ALERT_ICONS.get(atype, "📋")

                    # Group correlation banner (show once per group)
                    if group != "—" and group not in shown_group_banners:
                        g_tickets = groups.get(group, [])
                        if len(g_tickets) > 1:
                            st.warning(
                                f"🔗 **Group {group}** — {len(g_tickets)} tickets likely share the same root cause: "
                                f"`{'`  `'.join(g_tickets)}`"
                            )
                        shown_group_banners.add(group)

                    # Ticket row
                    with st.container(border=True):
                        c_sev, c_id, c_type, c_summary, c_actions = st.columns([1.2, 1.3, 1.5, 4, 1.5])

                        c_sev.markdown(f"{sev_icon} **{severity}**")
                        c_id.markdown(f"`{tid}`")
                        c_type.markdown(f"{a_icon} {atype}")
                        c_summary.markdown(summary)

                        with c_actions:
                            qa, qr = st.columns(2)
                            approve_q = qa.button("✅", key=f"qa_{tid}", use_container_width=True, help="Approve")
                            reject_q  = qr.button("❌", key=f"qr_{tid}", use_container_width=True, help="Reject")

                        if approve_q or reject_q:
                            status = "Approved (Queue)" if approve_q else "Rejected"
                            # Get category from df
                            row = df[df["Ticket_ID"] == tid]
                            cat = row.iloc[0]["Category"] if not row.empty else "Unknown"
                            if approve_q:
                                alert_msg = row.iloc[0].get("Alert_Message", tid) if not row.empty else tid
                                glpi_id = _glpi_create_ticket(
                                    f"[NOC] {alert_msg}",
                                    f"Ticket ID: {tid}\nCategory: {cat}\nSeverity: {severity}\nApproved from NOC Queue View.",
                                    severity
                                )
                                st.toast(f"GLPI Ticket #{glpi_id} created", icon="🎫")
                            st.session_state.processed_tickets.append({
                                "Ticket_ID":        tid,
                                "Category":         cat,
                                "Severity":         severity,
                                "Status":           status,
                                "Response_Time_Secs": 0,
                                "SLA_Breached":     False,
                                "Correlated_With":  group if group != "—" else "",
                                "Confidence_Score": "",
                            })
                            save_processed_tickets(st.session_state.processed_tickets)
                            st.session_state.queue_scan_results = [
                                x for x in st.session_state.queue_scan_results if x["ticket_id"] != tid
                            ]
                            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("📈 NOC/SOC Performance Metrics")

    if not st.session_state.processed_tickets:
        st.info("No data yet. Go to 'Live Operations' and start processing tickets to see metrics here.")
    else:
        metrics_df = pd.DataFrame(st.session_state.processed_tickets)
        sla_breached_count = int(metrics_df["SLA_Breached"].sum()) if "SLA_Breached" in metrics_df.columns else 0
        approved_count_m   = len(metrics_df[metrics_df["Status"].isin(["Approved", "Approved (Queue)"])])
        rejected_count_m   = len(metrics_df[metrics_df["Status"] == "Rejected"])
        duplicate_count_m  = len(metrics_df[metrics_df["Status"] == "Dropped (Duplicate)"])

        # ── Row 1: KPI cards ─────────────────────────────────────────────────
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Processed",    len(metrics_df))
        m2.metric("Approved ✅",         approved_count_m)
        m3.metric("Rejected ❌",         rejected_count_m)
        m4.metric("Duplicates 🗑️",      duplicate_count_m)
        m5.metric("SLA Breached 🚨",     sla_breached_count)

        # Avg confidence score
        if "Confidence_Score" in metrics_df.columns:
            scores = pd.to_numeric(metrics_df["Confidence_Score"], errors="coerce").dropna()
            avg_conf = int(scores.mean()) if not scores.empty else 0
        else:
            avg_conf = 0
        m6.metric("Avg Confidence 🎯",  f"{avg_conf}%")

        st.divider()

        # ── Row 2: Category pie + Severity pie ───────────────────────────────
        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("**Tickets by Category**")
            cat_counts = metrics_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig_cat = px.pie(
                cat_counts, names="Category", values="Count",
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.4,
            )
            fig_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_cat.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, height=300)
            st.plotly_chart(fig_cat, use_container_width=True)

        with ch2:
            st.markdown("**Tickets by Severity**")
            sev_order   = ["Critical", "High", "Medium", "Low"]
            sev_colors  = {"Critical": "#d62728", "High": "#ff7f0e",
                           "Medium": "#f0c419",   "Low":  "#2ca02c"}
            sev_counts  = metrics_df["Severity"].value_counts().reindex(sev_order).dropna().reset_index()
            sev_counts.columns = ["Severity", "Count"]
            fig_sev = px.bar(
                sev_counts, x="Severity", y="Count",
                color="Severity", color_discrete_map=sev_colors,
                text="Count",
            )
            fig_sev.update_traces(textposition="outside")
            fig_sev.update_layout(
                showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                height=300, xaxis_title="", yaxis_title="Count",
            )
            st.plotly_chart(fig_sev, use_container_width=True)

        # ── Row 3: Ticket volume over time + Status breakdown ────────────────
        ch3, ch4 = st.columns(2)

        with ch3:
            st.markdown("**Ticket Volume Over Time**")
            if "Timestamp" in metrics_df.columns:
                time_df = metrics_df.copy()
                time_df["Timestamp"] = pd.to_datetime(time_df["Timestamp"], errors="coerce")
                time_df = time_df.dropna(subset=["Timestamp"])
                time_df["Hour"] = time_df["Timestamp"].dt.floor("H")
                vol = time_df.groupby("Hour").size().reset_index(name="Count")
                fig_vol = px.line(
                    vol, x="Hour", y="Count",
                    markers=True, line_shape="spline",
                    color_discrete_sequence=["#636efa"],
                )
                fig_vol.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=300,
                    xaxis_title="Time", yaxis_title="Tickets",
                )
                st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.info("No timestamp data available.")

        with ch4:
            st.markdown("**Status Breakdown by Category**")
            if "Category" in metrics_df.columns and "Status" in metrics_df.columns:
                grp = metrics_df.groupby(["Category", "Status"]).size().reset_index(name="Count")
                fig_grp = px.bar(
                    grp, x="Category", y="Count", color="Status",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    barmode="stack", text="Count",
                )
                fig_grp.update_traces(textposition="inside")
                fig_grp.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=300,
                    xaxis_title="", yaxis_title="Count", legend_title="Status",
                )
                st.plotly_chart(fig_grp, use_container_width=True)

        # ── Row 4: Confidence score distribution + Top devices ───────────────
        ch5, ch6 = st.columns(2)

        with ch5:
            st.markdown("**AI Confidence Score Distribution**")
            if "Confidence_Score" in metrics_df.columns:
                conf_df = metrics_df.copy()
                conf_df["Confidence_Score"] = pd.to_numeric(
                    conf_df["Confidence_Score"], errors="coerce"
                ).dropna()
                if not conf_df["Confidence_Score"].dropna().empty:
                    fig_conf = px.histogram(
                        conf_df.dropna(subset=["Confidence_Score"]),
                        x="Confidence_Score", nbins=10,
                        color_discrete_sequence=["#00cc96"],
                        range_x=[0, 100],
                    )
                    fig_conf.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10), height=300,
                        xaxis_title="Confidence Score (%)", yaxis_title="Tickets",
                        bargap=0.1,
                    )
                    st.plotly_chart(fig_conf, use_container_width=True)
                else:
                    st.info("No confidence scores recorded yet.")
            else:
                st.info("No confidence score data.")

        with ch6:
            st.markdown("**SLA Status by Severity**")
            if "SLA_Breached" in metrics_df.columns and "Severity" in metrics_df.columns:
                sla_df = metrics_df.copy()
                sla_df["SLA_Status"] = sla_df["SLA_Breached"].apply(
                    lambda x: "Breached 🔴" if x else "Within SLA 🟢"
                )
                sla_grp = sla_df.groupby(["Severity", "SLA_Status"]).size().reset_index(name="Count")
                fig_sla = px.bar(
                    sla_grp, x="Severity", y="Count", color="SLA_Status",
                    color_discrete_map={"Breached 🔴": "#d62728", "Within SLA 🟢": "#2ca02c"},
                    barmode="group", text="Count",
                    category_orders={"Severity": sev_order},
                )
                fig_sla.update_traces(textposition="outside")
                fig_sla.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=300,
                    xaxis_title="", yaxis_title="Count", legend_title="SLA",
                )
                st.plotly_chart(fig_sla, use_container_width=True)
            else:
                st.info("No SLA data available.")

        # ── Detailed Audit Log ────────────────────────────────────────────────
        st.divider()
        st.markdown("**📋 Detailed Audit Log**")

        # Filter controls
        fc1, fc2, fc3 = st.columns(3)
        f_cat = fc1.multiselect(
            "Filter by Category",
            options=metrics_df["Category"].unique().tolist(),
            default=[],
        )
        f_sev = fc2.multiselect(
            "Filter by Severity",
            options=["Critical", "High", "Medium", "Low"],
            default=[],
        )
        f_status = fc3.multiselect(
            "Filter by Status",
            options=metrics_df["Status"].unique().tolist(),
            default=[],
        )

        filtered_df = metrics_df.copy()
        if f_cat:
            filtered_df = filtered_df[filtered_df["Category"].isin(f_cat)]
        if f_sev:
            filtered_df = filtered_df[filtered_df["Severity"].isin(f_sev)]
        if f_status:
            filtered_df = filtered_df[filtered_df["Status"].isin(f_status)]

        st.caption(f"Showing {len(filtered_df)} of {len(metrics_df)} tickets")
        st.dataframe(filtered_df, use_container_width=True, height=350)

        st.divider()

        # ── Shift Handoff Report ──────────────────────────────────────────────
        st.subheader("📋 Shift Handoff Report")

        hf1, hf2, hf3, hf4 = st.columns([2, 2, 2, 2])
        outgoing_eng = hf1.text_input("Outgoing Engineer", placeholder="e.g. Ahmed Al-Rashidi")
        incoming_eng = hf2.text_input("Incoming Engineer", placeholder="e.g. Sara Khalil")
        shift_period = hf3.text_input("Shift Period",       placeholder="e.g. 08:00 – 16:00")
        report_mode  = hf4.radio(
            "Report Mode",
            options=["Quick (1 page)", "Full (7 sections)"],
            index=0,
            help="Quick: Open items + metrics + watch list only. Full: all sections including critical summaries and full log.",
            horizontal=True,
        )
        short_mode = (report_mode == "Quick (1 page)")

        st.caption(
            "**Quick** — ~1 page, engineer-to-engineer essentials only.  "
            "**Full** — complete 7-section report with AI narratives, incident log and correlations."
        )

        gen_col, dl_col, excel_col, _ = st.columns([1.4, 1.4, 1.4, 1.8])

        with gen_col:
            if st.button("🔄 Generate Handoff Report", type="primary", use_container_width=True):
                with st.spinner("AI is writing the report… (~15 seconds)"):
                    try:
                        pending    = get_pending_tickets()
                        ai_content = run_handoff_llm(
                            st.session_state.processed_tickets, pending
                        )
                        buf = generate_handoff_report_doc(
                            tickets_data    = st.session_state.processed_tickets,
                            pending_tickets = pending,
                            outgoing_eng    = outgoing_eng,
                            incoming_eng    = incoming_eng,
                            shift_period    = shift_period,
                            ai_content      = ai_content,
                            short_mode      = short_mode,
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
                    use_container_width = True,
                )
            else:
                st.button("📄 Download Handoff (.docx)", disabled=True, use_container_width=True)

        with excel_col:
            excel_buf = generate_excel_report(st.session_state.processed_tickets)
            st.download_button(
                label     = "📊 Download Excel Log (.xlsx)",
                data      = excel_buf,
                file_name = f"NOC_Audit_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width = True,
            )

        if st.session_state.handoff_ready:
            st.success("✅ Report ready — click **Download Handoff (.docx)** to save it.")

# ─── Auto-Scan Engine ────────────────────────────────────────────────────────
if st.session_state.auto_scan_enabled and not st.session_state.waiting_for_user:
    if st.session_state.ticket_index < len(df):
        time_since_last = time.time() - st.session_state.last_auto_scan
        if time_since_last >= AUTO_SCAN_INTERVAL:
            st.session_state.is_scanning = True
            st.session_state.last_auto_scan = time.time()
            st.session_state.last_checked_display = datetime.now().strftime("%H:%M:%S")
            analyze_current_ticket()
            st.rerun()
        else:
            time.sleep(1)
            st.rerun()
