from datetime import datetime, time, timedelta

from enforcer.enforcer import FocusEnforcer
from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger
from enforcer.models import Site
from enforcer.rules import BudgetRule, ScheduleRule


def _make_enforcer(tmp_path):
    site = Site(
        name="reddit",
        hostnames=["reddit.com"],
        daily_budget_minutes=10,
        rules=[BudgetRule()],
    )
    ledger = UsageLedger(tmp_path / "state.json")
    blocker = HostsFileBlocker(tmp_path / "hosts")
    (tmp_path / "hosts").write_text("")
    enforcer = FocusEnforcer(sites=[site], ledger=ledger, blocker=blocker)
    return enforcer, site, ledger, blocker


def test_sync_blocks_site_by_default(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)

    enforcer.sync(now)

    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content


def test_unlock_grants_access_and_sync_reflects_it(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)

    granted = enforcer.unlock("reddit", 5, now)

    assert granted is True
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" not in content


def test_unlock_refuses_when_budget_exhausted(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 10, now)  # spends the full daily budget

    later = datetime(2026, 7, 31, 9, 30)
    granted = enforcer.unlock("reddit", 5, later)

    assert granted is False


def test_sync_aggregates_hostnames_from_all_blocked_sites(tmp_path):
    reddit = Site(
        name="reddit",
        hostnames=["reddit.com"],
        daily_budget_minutes=10,
        rules=[BudgetRule()],
    )
    twitter = Site(
        name="twitter",
        hostnames=["twitter.com", "x.com"],
        daily_budget_minutes=10,
        rules=[BudgetRule()],
    )
    ledger = UsageLedger(tmp_path / "state.json")
    blocker = HostsFileBlocker(tmp_path / "hosts")
    (tmp_path / "hosts").write_text("")
    enforcer = FocusEnforcer(sites=[reddit, twitter], ledger=ledger, blocker=blocker)
    now = datetime(2026, 7, 31, 9, 0)

    # Unlock only twitter; reddit stays blocked.
    enforcer.unlock("twitter", 5, now)

    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content
    assert "127.0.0.1 twitter.com" not in content
    assert "127.0.0.1 x.com" not in content


def test_unlock_unknown_site_raises(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)

    try:
        enforcer.unlock("nonexistent", 5, now)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_unlock_fails_when_schedule_rule_still_blocks_site(tmp_path):
    # Reddit has both a BudgetRule and a ScheduleRule covering 9:00-17:00.
    # An unlock attempt during that window has budget available but the
    # site must remain blocked in /etc/hosts, and unlock() must report
    # failure rather than falsely claiming success.
    site = Site(
        name="reddit",
        hostnames=["reddit.com"],
        daily_budget_minutes=10,
        rules=[BudgetRule(), ScheduleRule(start=time(9, 0), end=time(17, 0))],
    )
    ledger = UsageLedger(tmp_path / "state.json")
    blocker = HostsFileBlocker(tmp_path / "hosts")
    (tmp_path / "hosts").write_text("")
    enforcer = FocusEnforcer(sites=[site], ledger=ledger, blocker=blocker)
    now = datetime(2026, 7, 31, 10, 0)  # within the scheduled block window

    granted = enforcer.unlock("reddit", 5, now)

    assert granted is False
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content


def test_sync_reblocks_site_after_unlock_window_expires(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    start = datetime(2026, 7, 31, 9, 0)

    granted = enforcer.unlock("reddit", 5, start)
    assert granted is True
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" not in content

    after_expiry = start + timedelta(minutes=6)
    enforcer.sync(after_expiry)

    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content
