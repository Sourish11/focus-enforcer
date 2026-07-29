from datetime import datetime, time
from types import SimpleNamespace

from enforcer.ledger import UsageLedger
from enforcer.rules import BudgetRule, ScheduleRule


def test_budget_rule_blocks_when_not_unlocked(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    site = SimpleNamespace(name="reddit")
    now = datetime(2026, 7, 31, 9, 0)
    rule = BudgetRule()
    assert rule.is_blocked(site, now, ledger) is True


def test_budget_rule_unblocks_after_unlock(tmp_path):
    ledger = UsageLedger(tmp_path / "state.json")
    site = SimpleNamespace(name="reddit")
    now = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 10, now)
    rule = BudgetRule()
    assert rule.is_blocked(site, now, ledger) is False


def test_schedule_rule_blocks_inside_window():
    site = SimpleNamespace(name="reddit")
    rule = ScheduleRule(start=time(9, 0), end=time(17, 0))
    inside = datetime(2026, 7, 31, 12, 0)
    assert rule.is_blocked(site, inside, ledger=None) is True


def test_schedule_rule_allows_outside_window():
    site = SimpleNamespace(name="reddit")
    rule = ScheduleRule(start=time(9, 0), end=time(17, 0))
    outside = datetime(2026, 7, 31, 20, 0)
    assert rule.is_blocked(site, outside, ledger=None) is False
