"""
Emircom NOC — Runbook Retrieval Agent (RAG)

LLM-based retrieval over local JSON runbooks in data/emircom_runbooks/.
No vector DB, no GPU, no HuggingFace — uses the same raw Groq SDK shim
that the rest of the agent graph uses (_LazyLLM from agent_graph.py).

Public API:
    load_runbooks()                          -> list[dict]
    find_matching_runbook(description, logs, category, llm) -> str
        Returns a formatted runbook string ready to display in the HITL panel.
        Returns "" if no runbook matches with confidence >= 50.
"""

import json
import os
from pathlib import Path

# Resolve runbooks directory relative to this file's location
_RUNBOOKS_DIR = Path(__file__).parent.parent / "data" / "emircom_runbooks"


def load_runbooks() -> list:
    """Load and return all .json runbooks from the runbooks directory."""
    runbooks = []
    if not _RUNBOOKS_DIR.exists():
        return runbooks
    for f in sorted(_RUNBOOKS_DIR.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                rb = json.load(fh)
                # Ensure required fields exist
                if "id" in rb and "title" in rb:
                    runbooks.append(rb)
        except Exception as e:
            print(f"[RAG] ⚠️ Could not load runbook {f.name}: {e}")
    return runbooks


def _format_runbook(rb: dict, confidence: int, reason: str) -> str:
    """Format a runbook dict into a clean string for the HITL panel."""
    steps = rb.get("steps", [])
    steps_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(steps)])

    resolution   = rb.get("resolution", "See runbook for resolution steps.")
    escalation   = rb.get("escalation", "Escalate to Team Lead if unresolved.")
    eta          = rb.get("estimated_resolution_time", "Unknown")
    services     = ", ".join(rb.get("affected_services", []))
    reference    = rb.get("reference", "")

    lines = [
        f"**{rb['id']} — {rb['title']}**",
        f"Match confidence: {confidence}%  |  ETA: {eta}",
        f"_Reason: {reason}_",
        "",
        "**📋 Diagnosis Steps:**",
        steps_text,
        "",
        f"**✅ Resolution:** {resolution}",
        "",
        f"**🚨 Escalation:** {escalation}",
    ]
    if services:
        lines.append(f"\n**⚡ Affected Services:** {services}")
    if reference:
        lines.append(f"**📚 Reference:** {reference}")

    return "\n".join(lines)


def find_matching_runbook(description: str, logs: str, category: str, llm) -> str:
    """
    Use LLM to find the most relevant runbook for this alert.

    Parameters
    ----------
    description : str   — Alert description from AgentState
    logs        : str   — Raw logs from AgentState
    category    : str   — Category set by the Supervisor node
    llm         : _LazyLLM — The shared LLM shim from agent_graph.py

    Returns
    -------
    str — Formatted runbook text for display, or "" if no good match found.
    """
    runbooks = load_runbooks()
    if not runbooks:
        print("[RAG] ⚠️ No runbooks found in", _RUNBOOKS_DIR)
        return ""

    # Build a concise runbook index: id, title, triggers (to keep prompt small)
    index_lines = []
    for i, rb in enumerate(runbooks):
        triggers = ", ".join(rb.get("alert_triggers", [])[:5])
        index_lines.append(
            f"  [{i}] {rb['id']} — {rb['title']} | Category: {rb.get('category', '?')} | Triggers: {triggers}"
        )
    index_str = "\n".join(index_lines)

    # Truncate logs to avoid blowing the prompt budget
    logs_snippet = (logs or "")[:600].strip()

    prompt = f"""You are the Emircom NOC Runbook Retrieval System.

Your job: given an incoming alert, find the SINGLE best matching runbook from the list below.

ALERT:
  Description: {description}
  Logs: {logs_snippet}
  Category: {category}

AVAILABLE RUNBOOKS:
{index_str}

INSTRUCTIONS:
- Pick the runbook whose alert_triggers and title best match this alert.
- Assign a confidence score (0-100) based on how well the runbook matches.
- If no runbook matches well (confidence < 50), return match_index -1.
- Consider the category as a strong signal (Network alert → prefer Network runbooks).

Respond ONLY with valid JSON, no markdown, no explanation:
{{"match_index": 2, "confidence": 88, "reason": "BGP session down matches RB-NET-002 triggers exactly"}}"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        idx        = int(parsed.get("match_index", -1))
        confidence = int(parsed.get("confidence", 0))
        reason     = parsed.get("reason", "")

        if idx < 0 or confidence < 50 or idx >= len(runbooks):
            print(f"[RAG] No strong runbook match (confidence={confidence}, idx={idx})")
            return ""

        rb = runbooks[idx]
        print(f"[RAG] ✅ Matched {rb['id']} — {rb['title']} ({confidence}% confidence)")
        return _format_runbook(rb, confidence, reason)

    except json.JSONDecodeError as e:
        print(f"[RAG] ⚠️ JSON parse error in LLM response: {e}")
        return ""
    except Exception as e:
        print(f"[RAG] ❌ Retrieval error: {type(e).__name__}: {e}")
        return ""


def get_runbook_count() -> int:
    """Quick utility — returns how many runbooks are loaded."""
    return len(load_runbooks())
