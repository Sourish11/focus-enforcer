from datetime import datetime, timedelta
from enforcer.ledger import UsageLedger


def test_new_ledger_has_no_usage_and_is_locked(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    now = datetime(2026, 7, 31, 9, 0)
    assert ledger.minutes_used_today("reddit", now) == 0.0
    assert ledger.is_currently_unlocked("reddit", now) is False


def test_spend_and_unlock_records_usage_and_unlocks(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    now = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 10, now)
    assert ledger.minutes_used_today("reddit", now) == 10.0
    assert ledger.is_currently_unlocked("reddit", now) is True


def test_unlock_expires_after_granted_minutes(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    start = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 10, start)
    later = start + timedelta(minutes=11)
    assert ledger.is_currently_unlocked("reddit", later) is False


def test_usage_persists_across_ledger_instances(tmp_path):
    state_path = tmp_path / "state.json"
    first = UsageLedger(state_path)
    now = datetime(2026, 7, 31, 9, 0)
    first.spend_and_unlock("reddit", 5, now)

    second = UsageLedger(state_path)
    assert second.minutes_used_today("reddit", now) == 5.0


def test_usage_does_not_carry_over_to_next_day(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    day1 = datetime(2026, 7, 31, 23, 0)
    ledger.spend_and_unlock("reddit", 15, day1)
    day2 = datetime(2026, 8, 1, 0, 5)
    assert ledger.minutes_used_today("reddit", day2) == 0.0


def test_spend_and_unlock_accumulates_across_calls_same_day(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    now = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 5, now)
    ledger.spend_and_unlock("reddit", 5, now)
    assert ledger.minutes_used_today("reddit", now) == 10.0
