from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

import yaml

from enforcer.models import Override, Site
from enforcer.rules import BudgetRule, ScheduleRule


@dataclass
class Config:
    sites: list[Site]
    enforcement_interval_seconds: int


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


def build_site(
    name: str,
    hostnames: list[str],
    daily_budget_minutes: int,
    schedule_start: time | None = None,
    schedule_end: time | None = None,
    override: Override = None,
) -> Site:
    rules: list = [BudgetRule()]
    if schedule_start is not None and schedule_end is not None:
        rules.append(ScheduleRule(start=schedule_start, end=schedule_end))
    return Site(
        name=name,
        hostnames=list(hostnames),
        daily_budget_minutes=daily_budget_minutes,
        rules=rules,
        override=override,
    )


def site_schedule(site: Site) -> ScheduleRule | None:
    for rule in site.rules:
        if isinstance(rule, ScheduleRule):
            return rule
    return None


def _site_to_raw(site: Site) -> dict:
    raw: dict = {
        "name": site.name,
        "hostnames": list(site.hostnames),
        "daily_budget_minutes": site.daily_budget_minutes,
    }
    schedule = site_schedule(site)
    if schedule is not None:
        raw["scheduled_block"] = {
            "start": _format_time(schedule.start),
            "end": _format_time(schedule.end),
        }
    if site.override is not None:
        raw["override"] = site.override
    return raw


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())

    sites: list[Site] = []
    for raw_site in raw["sites"]:
        scheduled_block = raw_site.get("scheduled_block")
        schedule_start = None
        schedule_end = None
        if scheduled_block is not None:
            schedule_start = _parse_time(scheduled_block["start"])
            schedule_end = _parse_time(scheduled_block["end"])
        override = raw_site.get("override")
        if override not in (None, "allow", "block"):
            raise TypeError(f"Invalid override for site {raw_site.get('name')!r}: {override!r}")
        sites.append(
            build_site(
                name=raw_site["name"],
                hostnames=raw_site["hostnames"],
                daily_budget_minutes=raw_site["daily_budget_minutes"],
                schedule_start=schedule_start,
                schedule_end=schedule_end,
                override=override,
            )
        )

    return Config(
        sites=sites,
        enforcement_interval_seconds=raw.get("enforcement_interval_seconds", 30),
    )


def save_config(path: Path, config: Config) -> None:
    path = Path(path)
    raw = {
        "sites": [_site_to_raw(site) for site in config.sites],
        "enforcement_interval_seconds": config.enforcement_interval_seconds,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
