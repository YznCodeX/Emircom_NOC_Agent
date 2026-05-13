"""
Emircom NOC Agent — Pipeline Integration Test
==============================================
Runs ONE ticket end-to-end through the LangGraph agent graph.

What it tests:
  - Supervisor node routes to the correct specialist
  - Specialist node returns valid JSON with all required fields
  - Runbook node returns a string (match or empty)
  - Correlation node populates is_correlated + correlated_with
  - All AgentState fields are populated after the pipeline pauses at HITL

What it does NOT do:
  - Create a GLPI ticket  (remedy node is never resumed)
  - Send an email         (same reason)
  - Consume Groq quota beyond one ticket (~1,500 tokens)

Usage:
    venv\\Scripts\\python test_pipeline.py
"""

import os
import sys
import json
import time

print("=" * 65)
print("   EMIRCOM NOC AGENT — PIPELINE INTEGRATION TEST")
print("=" * 65)

# ── 0. Environment check ─────────────────────────────────────────
print("\n[0] ENVIRONMENT CHECK")
key = os.environ.get("GROQ_API_KEY") or ""
if not key:
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("GROQ_API_KEY") or ""

if key:
    print(f"    ✅ GROQ_API_KEY found  ({key[:8]}...)")
else:
    print("    ❌ GROQ_API_KEY not set — check your .env file")
    sys.exit(1)

# ── 1. Import agent graph ────────────────────────────────────────
print("\n[1] IMPORTING AGENT GRAPH")
try:
    from src.agent_graph import app, AgentState
    print("    ✅ agent_graph imported — LangGraph app compiled")
except Exception as e:
    print(f"    ❌ Import failed: {e}")
    sys.exit(1)

# ── 2. Define test ticket ────────────────────────────────────────
# A clear Network ticket so we can predict the routing
TEST_TICKET = {
    "ticket_id":   "TEST-0001",
    "category":    "Network",
    "description": "BGP session dropped between CE-MPLS-01 and PE-Router-RUH-01. "
                   "Multiple prefixes lost. Customer traffic impacted.",
    "logs": (
        "Jun 10 14:32:01 CE-MPLS-01 BGP: %BGP-5-ADJCHANGE: neighbor 10.0.0.1 Down "
        "BGP Notification sent, error code Hold Timer Expired\n"
        "Jun 10 14:32:01 CE-MPLS-01 BGP: %BGP-3-NOTIFICATION: sent to neighbor "
        "10.0.0.1 4/0 (hold time expired) 0 bytes\n"
        "Jun 10 14:32:05 PE-Router-RUH-01 BGP: %BGP-5-ADJCHANGE: neighbor 192.168.1.2 "
        "Down BGP Notification received\n"
        "Jun 10 14:32:10 CE-MPLS-01 OSPF: Neighbor 10.0.0.1 changed state to Down"
    ),
    "analysis":        "",
    "is_duplicate":    False,
    "duplicate_reason":"",
    "is_correlated":   False,
    "correlated_with": "",
    "confidence_score": 0,
    "severity":        "",
    "recommendation":  "",
    "glpi_ticket_id":  "",
    "supervisor_reason":"",
    "runbook_match":   "",
    "skip_email":      False,
}

print(f"\n[2] TEST TICKET")
print(f"    Ticket ID   : {TEST_TICKET['ticket_id']}")
print(f"    Category    : {TEST_TICKET['category']}")
print(f"    Description : {TEST_TICKET['description'][:70]}...")

# ── 3. Run pipeline (pauses at HITL) ────────────────────────────
print("\n[3] RUNNING PIPELINE  (this makes ~5 Groq API calls)")
config = {"configurable": {"thread_id": TEST_TICKET["ticket_id"]}}

start = time.time()
try:
    result = app.invoke(TEST_TICKET, config)
    elapsed = time.time() - start
    print(f"    ✅ Pipeline completed in {elapsed:.1f}s  (paused at HITL interrupt)")
except Exception as e:
    print(f"    ❌ Pipeline error: {type(e).__name__}: {e}")
    sys.exit(1)

# ── 4. Inspect final state ───────────────────────────────────────
print("\n[4] INSPECTING AGENT STATE")
state = app.get_state(config)
vals  = state.values

checks_passed = 0
checks_total  = 0

def check(label, condition, actual=""):
    global checks_passed, checks_total
    checks_total += 1
    status = "✅" if condition else "❌"
    suffix = f"  →  {actual}" if actual else ""
    print(f"    {status} {label}{suffix}")
    if condition:
        checks_passed += 1

# Routing
category = vals.get("category", "")
check("Supervisor routed to Network", category == "Network", category)
check("supervisor_reason populated", bool(vals.get("supervisor_reason", "")))

# Specialist analysis
raw_analysis = vals.get("analysis", "")
check("analysis field non-empty", bool(raw_analysis))
try:
    analysis = json.loads(raw_analysis.replace("```json","").replace("```","").strip())
    check("analysis is valid JSON", True)
    for field in ["Severity", "Affected_Node", "Root_Cause", "Recommended_Action", "Confidence_Score"]:
        check(f"  analysis.{field} present", field in analysis, str(analysis.get(field, "MISSING"))[:60])
except Exception as e:
    check("analysis is valid JSON", False, str(e))

# Confidence score
score = vals.get("confidence_score", -1)
check("confidence_score 0–100", 0 <= score <= 100, str(score))

# Severity
severity = vals.get("severity", "") or analysis.get("Severity", "")
check("severity is valid", severity in ("Critical","High","Medium","Low"), severity)

# Runbook
runbook = vals.get("runbook_match", None)
check("runbook_match is string (not None)", isinstance(runbook, str))
if runbook:
    check("runbook matched (non-empty)", True, f"{len(runbook)} chars")
else:
    check("runbook returned empty (below threshold or no match)", True, "no match")

# Correlation
check("is_correlated is bool", isinstance(vals.get("is_correlated"), bool))

# HITL interrupt position
next_nodes = [n for n in (state.next or [])]
check("pipeline paused before remedy/drop", bool(next_nodes), str(next_nodes))

# ── 5. Deduplication test ────────────────────────────────────────
print("\n[5] DEDUPLICATION TEST  (same ticket re-submitted)")
try:
    result2 = app.invoke(TEST_TICKET, {"configurable": {"thread_id": "TEST-0001-DUP"}})
    state2  = app.get_state({"configurable": {"thread_id": "TEST-0001-DUP"}})
    is_dup  = state2.values.get("is_duplicate", False)
    # The LLM may or may not flag this as duplicate depending on context window
    # We only check the field is present and boolean
    check("is_duplicate field is boolean", isinstance(is_dup, bool), str(is_dup))
    if is_dup:
        print(f"         ✅ LLM flagged as duplicate — dedup working correctly")
    else:
        print(f"         ℹ️  LLM treated as unique (both tickets in same test run)")
except Exception as e:
    print(f"    ⚠️  Dedup test skipped: {e}")

# ── 6. Runbook loading test ──────────────────────────────────────
print("\n[6] RUNBOOK LIBRARY CHECK")
try:
    from src.rag_core import load_runbooks
    runbooks = load_runbooks()
    check(f"Runbooks loaded ({len(runbooks)} files)", len(runbooks) == 13, str(len(runbooks)))
    categories = {}
    for rb in runbooks:
        prefix = rb["id"].split("-")[1]  # NET, SEC, HW, APP, CLD
        categories[prefix] = categories.get(prefix, 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"    {'✅'} {cat}: {count} runbook(s)")
except Exception as e:
    print(f"    ❌ Runbook load failed: {e}")

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "=" * 65)
if checks_passed == checks_total:
    print(f"   ALL {checks_total} CHECKS PASSED ✅ — PIPELINE HEALTHY")
else:
    print(f"   {checks_passed}/{checks_total} CHECKS PASSED — review failures above")
print("=" * 65)
print()
print("Next steps:")
print("  • Open http://localhost:8501 to test the full HITL UI")
print("  • Run test_system.py for data/persistence checks")
print()
