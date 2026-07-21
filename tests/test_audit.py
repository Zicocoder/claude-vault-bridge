"""Tests for the JSONL audit log, writing to a tmp path (no config needed)."""

from __future__ import annotations

from claude_vault_bridge import audit


def test_log_writes_one_event(tmp_path):
    p = tmp_path / "events.jsonl"
    audit.log("example.com", "approved", 1234, source="hotkey", path=p, timestamp="2026-07-21T00:00:00+00:00")
    events = audit.read_events(p)
    assert events == [
        {
            "ts": "2026-07-21T00:00:00+00:00",
            "domain": "example.com",
            "decision": "approved",
            "latency_ms": 1234,
            "source": "hotkey",
        }
    ]


def test_log_appends(tmp_path):
    p = tmp_path / "events.jsonl"
    audit.log("a.com", "approved", 1, path=p)
    audit.log("b.com", "denied", 2, path=p)
    events = audit.read_events(p)
    assert [e["domain"] for e in events] == ["a.com", "b.com"]
    assert [e["decision"] for e in events] == ["approved", "denied"]


def test_log_creates_missing_parent_dir(tmp_path):
    p = tmp_path / "nested" / "deep" / "events.jsonl"
    audit.log("x.com", "timeout", 60000, path=p)
    assert p.exists()


def test_log_never_contains_credential_fields(tmp_path):
    p = tmp_path / "events.jsonl"
    audit.log("example.com", "approved", 10, path=p)
    (event,) = audit.read_events(p)
    assert set(event) == {"ts", "domain", "decision", "latency_ms", "source"}


def test_read_missing_file_is_empty(tmp_path):
    assert audit.read_events(tmp_path / "nope.jsonl") == []
