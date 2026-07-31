from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

import yaml

from enforcer.models import Site
from enforcer.rules import BudgetRule, ScheduleRule


@dataclass
class Config:
    sites: list[Site]
    enforcement_interval_seconds: int


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())

    sites: list[Site] = []
    for raw_site in raw["sites"]:
        rules = [BudgetRule()]
        scheduled_block = raw_site.get("scheduled_block")
        if scheduled_block is not None:
            rules.append(
                ScheduleRule(
                    start=_parse_time(scheduled_block["start"]),
                    end=_parse_time(scheduled_block["end"]),
                )
            )
        sites.append(
            Site(
                name=raw_site["name"],
                hostnames=raw_site["hostnames"],
                daily_budget_minutes=raw_site["daily_budget_minutes"],
                rules=rules,
            )
        )

    return Config(
        sites=sites,
        enforcement_interval_seconds=raw.get("enforcement_interval_seconds", 30),
    )
