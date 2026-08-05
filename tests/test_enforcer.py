from datetime import datetime, time, timedelta

from enforcer.enforcer import FocusEnforcer
from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger
from enforcer.models import Site
from enforcer.rules import BudgetRule, ScheduleRule


def _make_enforcer(tmp_path, sites=None):
    if sites is None:
        sites = [
            Site(
                name="reddit",
                hostnames=["reddit.com"],
                daily_budget_minutes=10,
                rules=[BudgetRule()],
            )
        ]
    ledger = UsageLedger(tmp_path / "state.json")
    blocker = HostsFileBlocker(tmp_path / "hosts")
    (tmp_path / "hosts").write_text("")
    enforcer = FocusEnforcer(sites=sites, ledger=ledger, blocker=blocker)
    return enforcer, sites[0], ledger, blocker


def test_sync_blocks_site_by_default(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)

    enforcer.sync(now)

    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content


def test_unlock_grants_access_and_sync_reflects_it(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)

    result = enforcer.unlock("reddit", 5, now)

    assert result.granted is True
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" not in content


def test_unlock_refuses_when_budget_exhausted(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)
    ledger.spend_and_unlock("reddit", 10, now)  # spends the full daily budget

    later = datetime(2026, 7, 31, 9, 30)
    result = enforcer.unlock("reddit", 5, later)

    assert result.granted is False
    assert result.reason == "insufficient_budget"


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
    enforcer, _, ledger, blocker = _make_enforcer(tmp_path, sites=[reddit, twitter])
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
    enforcer, _, ledger, blocker = _make_enforcer(tmp_path, sites=[site])
    now = datetime(2026, 7, 31, 10, 0)  # within the scheduled block window

    result = enforcer.unlock("reddit", 5, now)

    assert result.granted is False
    assert result.reason == "still_blocked"
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content


def test_sync_reblocks_site_after_unlock_window_expires(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    start = datetime(2026, 7, 31, 9, 0)

    result = enforcer.unlock("reddit", 5, start)
    assert result.granted is True
    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" not in content

    after_expiry = start + timedelta(minutes=6)
    enforcer.sync(after_expiry)

    content = (tmp_path / "hosts").read_text()
    assert "127.0.0.1 reddit.com" in content


def test_lock_clears_unlock_and_reblocks(tmp_path):
    enforcer, site, ledger, blocker = _make_enforcer(tmp_path)
    now = datetime(2026, 7, 31, 9, 0)
    enforcer.unlock("reddit", 5, now)
    assert "127.0.0.1 reddit.com" not in (tmp_path / "hosts").read_text()

    enforcer.lock("reddit", now)

    assert ledger.is_currently_unlocked("reddit", now) is False
    assert "127.0.0.1 reddit.com" in (tmp_path / "hosts").read_text()
