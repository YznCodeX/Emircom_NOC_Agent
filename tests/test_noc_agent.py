"""
Emircom NOC Agent — Unit Test Suite
=====================================
Run with:  pytest tests/ -v

What is tested here (no LLM calls, runs in < 2 seconds):

  Group 1 — Hash dedup helpers   (_desc_hash, _dedup_hash_seen, _dedup_ticket_seen)
  Group 2 — JSON extraction       (extract_json from streamlit/helpers.py)
  Group 3 — SLA status calculator (get_sla_status from streamlit/helpers.py)

All database tests use an in-memory SQLite — they never touch the real data/noc_memory.db.
"""

import sqlite3
import time
import pytest

# ── imports from our own codebase ─────────────────────────────────────────────
from src.agent_graph import _desc_hash, _dedup_hash_seen, _dedup_ticket_seen, _dedup_add, _init_dedup_db
from helpers import extract_json, get_sla_status


# ── shared fixture: fresh in-memory DB for every test ─────────────────────────
@pytest.fixture
def db():
    """Create a clean in-memory SQLite dedup DB for each test.

    'in-memory' means it lives in RAM only — it disappears when the test ends.
    This keeps tests isolated: one test's data can never affect another.
    """
    conn = sqlite3.connect(":memory:")
    _init_dedup_db(conn)
    yield conn
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Hash Dedup Helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestDescHash:
    """Tests for _desc_hash — the MD5 fingerprint function we added today.

    A hash is just a fixed-length fingerprint of a string.
    The key properties we need: same input → same output, different input → different output.
    """

    def test_same_input_gives_same_hash(self):
        # Most fundamental requirement: deterministic
        text = "BGP session dropped on CE-MPLS-01. Hold timer expired."
        assert _desc_hash(text) == _desc_hash(text)

    def test_different_inputs_give_different_hashes(self):
        # Two different alerts must not collide
        hash1 = _desc_hash("BGP session dropped on CE-MPLS-01")
        hash2 = _desc_hash("Port flapping on Switch-Access-DMM-02")
        assert hash1 != hash2

    def test_case_insensitive(self):
        # "BGP SESSION DROPPED" and "bgp session dropped" should be treated as the same alert
        assert _desc_hash("BGP SESSION DROPPED") == _desc_hash("bgp session dropped")

    def test_strips_leading_trailing_whitespace(self):
        # Monitoring tools often pad alert text with spaces/newlines
        assert _desc_hash("  port flapping  ") == _desc_hash("port flapping")

    def test_returns_string(self):
        result = _desc_hash("any alert text")
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 is always 32 hex characters


class TestDedupHashSeen:
    """Tests for _dedup_hash_seen — checks if a description hash exists in the DB."""

    def test_returns_false_for_brand_new_description(self, db):
        h = _desc_hash("BGP session dropped on PE-Router-RUH-01")
        assert _dedup_hash_seen(db, h) is False

    def test_returns_true_after_same_description_is_added(self, db):
        description = "Port Gi1/0/12 flapping on Switch-Access-DMM-02. CRC errors."
        _dedup_add(db, "INC-3001", description)

        h = _desc_hash(description)
        assert _dedup_hash_seen(db, h) is True

    def test_does_not_match_different_description(self, db):
        _dedup_add(db, "INC-3001", "BGP dropped on router A")

        h = _desc_hash("High CPU on router B")  # completely different alert
        assert _dedup_hash_seen(db, h) is False


class TestDedupTicketSeen:
    """Tests for _dedup_ticket_seen — checks if a ticket ID was already processed."""

    def test_returns_false_for_new_ticket_id(self, db):
        assert _dedup_ticket_seen(db, "INC-9999") is False

    def test_returns_true_after_ticket_is_added(self, db):
        _dedup_add(db, "INC-3001", "some alert description")
        assert _dedup_ticket_seen(db, "INC-3001") is True

    def test_does_not_match_different_ticket_id(self, db):
        _dedup_add(db, "INC-3001", "some alert description")
        assert _dedup_ticket_seen(db, "INC-3002") is False


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — JSON Extraction (extract_json)
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractJson:
    """Tests for extract_json — parses LLM output that may have markdown fences.

    LLMs often wrap JSON in ```json ... ``` blocks or add surrounding text.
    This function handles all of that so the rest of the code always gets a plain dict.
    """

    def test_plain_json_string(self):
        raw = '{"Severity": "Critical", "Confidence_Score": 90}'
        result = extract_json(raw)
        assert result["Severity"] == "Critical"
        assert result["Confidence_Score"] == 90

    def test_json_wrapped_in_markdown_fences(self):
        # This is exactly what Groq LLaMA returns sometimes
        raw = '```json\n{"is_duplicate": false, "reason": "different device"}\n```'
        result = extract_json(raw)
        assert result["is_duplicate"] is False
        assert "reason" in result

    def test_json_with_surrounding_prose(self):
        # LLM adds explanation before/after the JSON
        raw = 'Here is my analysis:\n{"Severity": "High"}\nLet me know if you need more.'
        result = extract_json(raw)
        assert result["Severity"] == "High"

    def test_completely_invalid_input_returns_empty_dict(self):
        # Never raises — always returns a dict so callers don't crash
        result = extract_json("This is not JSON at all, just plain text.")
        assert result == {}

    def test_empty_string_returns_empty_dict(self):
        assert extract_json("") == {}


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — SLA Status Calculator (get_sla_status)
# ══════════════════════════════════════════════════════════════════════════════

class TestGetSlaStatus:
    """Tests for get_sla_status — calculates how much of the SLA window is used.

    SLA (Service Level Agreement) = the maximum time allowed to resolve a ticket.
    Critical = 15 min, High = 60 min, Medium = 240 min, Low = 1440 min.

    Returns: (elapsed_secs, remaining_secs, pct_used)
    pct_used >= 1.0 means SLA is breached.
    """

    def test_fresh_ticket_has_low_pct_used(self):
        start = time.time()  # just started — elapsed is ~0 seconds
        elapsed, remaining, pct = get_sla_status("Critical", start)
        assert pct < 0.1  # less than 10% used
        assert remaining > 0  # still time left

    def test_breached_ticket_has_pct_over_1(self):
        # Simulate a ticket that started 20 minutes ago on a Critical SLA (15 min limit)
        twenty_minutes_ago = time.time() - (20 * 60)
        elapsed, remaining, pct = get_sla_status("Critical", twenty_minutes_ago)
        assert pct > 1.0       # breached
        assert remaining < 0   # negative = overdue

    def test_unknown_severity_defaults_to_3600_seconds(self):
        start = time.time()
        elapsed, remaining, pct = get_sla_status("UNKNOWN_SEVERITY", start)
        # Default is 3600s — a fresh ticket should have ~100% remaining
        assert remaining > 3500

    def test_high_severity_has_longer_window_than_critical(self):
        # Critical SLA = 15 min, High SLA = 60 min
        # After 10 minutes, Critical is ~67% used, High is ~17% used
        ten_minutes_ago = time.time() - (10 * 60)
        _, _, pct_critical = get_sla_status("Critical", ten_minutes_ago)
        _, _, pct_high = get_sla_status("High", ten_minutes_ago)
        assert pct_critical > pct_high
