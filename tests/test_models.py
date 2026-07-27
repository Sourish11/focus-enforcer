from datetime import datetime
from enforcer.models import Site


class _FakeRule:
    def __init__(self, blocked: bool):
        self.blocked = blocked

    def is_blocked(self, site, now, ledger):
        return self.blocked


def test_site_blocked_if_any_rule_blocks():
    site = Site(
        name="reddit",
        hostnames=["reddit.com"],
        daily_budget_minutes=20,
        rules=[_FakeRule(False), _FakeRule(True)],
    )
    assert site.is_blocked(datetime(2026, 7, 31, 10, 0), ledger=None) is True


def test_site_unblocked_if_no_rule_blocks():
    site = Site(
        name="reddit",
        hostnames=["reddit.com"],
        daily_budget_minutes=20,
        rules=[_FakeRule(False), _FakeRule(False)],
    )
    assert site.is_blocked(datetime(2026, 7, 31, 10, 0), ledger=None) is False


def test_site_unblocked_with_no_rules():
    site = Site(name="reddit", hostnames=["reddit.com"], daily_budget_minutes=20)
    assert site.is_blocked(datetime(2026, 7, 31, 10, 0), ledger=None) is False
