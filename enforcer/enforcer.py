from __future__ import annotations

import time
from datetime import datetime

from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger
from enforcer.models import Site


class FocusEnforcer:
    def __init__(self, sites: list[Site], ledger: UsageLedger, blocker: HostsFileBlocker):
        self.sites = sites
        self.ledger = ledger
        self.blocker = blocker

    def sync(self, now: datetime) -> None:
        blocked_hostnames: list[str] = []
        for site in self.sites:
            if site.is_blocked(now, self.ledger):
                blocked_hostnames.extend(site.hostnames)
        self.blocker.set_blocked_hostnames(blocked_hostnames)

    def unlock(self, site_name: str, minutes: float, now: datetime) -> bool:
        site = self._find_site(site_name)
        if site is None:
            raise ValueError(f"Unknown site: {site_name}")

        if minutes <= 0:
            return False

        used = self.ledger.minutes_used_today(site.name, now)
        remaining = site.daily_budget_minutes - used
        if minutes > remaining:
            return False

        self.ledger.spend_and_unlock(site.name, minutes, now)
        self.sync(now)
        return site.is_blocked(now, self.ledger) is False

    def daemon(self, interval_seconds: int) -> None:
        while True:
            self.sync(datetime.now())
            time.sleep(interval_seconds)

    def _find_site(self, name: str) -> Site | None:
        return next((s for s in self.sites if s.name == name), None)
