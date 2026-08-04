from datetime import time

from enforcer.config import build_site, load_config, save_config
from enforcer.rules import BudgetRule, ScheduleRule


def test_load_config_parses_sites_and_interval(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sites:
  - name: reddit
    hostnames: [reddit.com]
    daily_budget_minutes: 20
  - name: youtube
    hostnames: [youtube.com]
    daily_budget_minutes: 30
    scheduled_block:
      start: "09:00"
      end: "17:00"
enforcement_interval_seconds: 45
"""
    )

    config = load_config(config_path)

    assert config.enforcement_interval_seconds == 45
    assert len(config.sites) == 2

    reddit = config.sites[0]
    assert reddit.name == "reddit"
    assert reddit.hostnames == ["reddit.com"]
    assert reddit.daily_budget_minutes == 20
    assert len(reddit.rules) == 1
    assert isinstance(reddit.rules[0], BudgetRule)

    youtube = config.sites[1]
    assert len(youtube.rules) == 2
    assert isinstance(youtube.rules[0], BudgetRule)
    schedule_rules = [r for r in youtube.rules if isinstance(r, ScheduleRule)]
    assert len(schedule_rules) == 1
    assert schedule_rules[0].start == time(9, 0)
    assert schedule_rules[0].end == time(17, 0)


def test_save_config_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sites:
  - name: reddit
    hostnames: [reddit.com, www.reddit.com]
    daily_budget_minutes: 20
  - name: youtube
    hostnames: [youtube.com]
    daily_budget_minutes: 30
    scheduled_block:
      start: "09:00"
      end: "17:00"
    override: allow
enforcement_interval_seconds: 45
"""
    )
    original = load_config(config_path)
    out_path = tmp_path / "out.yaml"
    save_config(out_path, original)
    reloaded = load_config(out_path)

    assert reloaded.enforcement_interval_seconds == 45
    assert len(reloaded.sites) == 2
    assert reloaded.sites[0].name == "reddit"
    assert reloaded.sites[0].hostnames == ["reddit.com", "www.reddit.com"]
    assert reloaded.sites[0].daily_budget_minutes == 20
    assert reloaded.sites[0].override is None
    assert len(reloaded.sites[0].rules) == 1
    assert isinstance(reloaded.sites[0].rules[0], BudgetRule)

    youtube = reloaded.sites[1]
    assert youtube.daily_budget_minutes == 30
    assert youtube.override == "allow"
    schedule_rules = [r for r in youtube.rules if isinstance(r, ScheduleRule)]
    assert schedule_rules[0].start == time(9, 0)
    assert schedule_rules[0].end == time(17, 0)


def test_build_site_with_and_without_schedule():
    plain = build_site("reddit", ["reddit.com"], 20)
    assert len(plain.rules) == 1
    assert isinstance(plain.rules[0], BudgetRule)

    scheduled = build_site(
        "youtube",
        ["youtube.com"],
        30,
        schedule_start=time(9, 0),
        schedule_end=time(17, 0),
    )
    assert len(scheduled.rules) == 2
    assert isinstance(scheduled.rules[1], ScheduleRule)
