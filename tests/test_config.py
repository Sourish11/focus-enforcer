from datetime import time

from enforcer.config import load_config
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
