from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger
from enforcer.models import Site
from enforcer.network_blocker import NetworkBlocker, NullNetworkBlocker


@dataclass(frozen=True)
class UnlockResult:
    granted: bool
    reason: str  # "granted", "insufficient_budget", "still_blocked", or "permanently_blocked"


class FocusEnforcer:
    def __init__(
        self,
        sites: list[Site],
        ledger: UsageLedger,
        blocker: HostsFileBlocker,
        network_blocker: NetworkBlocker | None = None,
    ):
        self.sites = sites
        self.ledger = ledger
        self.blocker = blocker
        self.network_blocker: NetworkBlocker = network_blocker or NullNetworkBlocker()

    def sync(self, now: datetime) -> None:
        blocked_hostnames: list[str] = []
        for site in self.sites:
            if site.is_blocked(now, self.ledger):
                blocked_hostnames.extend(site.hostnames)
        # Resolve + firewall first (uses public DNS), then hosts file.
        self.network_blocker.set_blocked_hostnames(blocked_hostnames)
        self.blocker.set_blocked_hostnames(blocked_hostnames)

    def unlock(self, site_name: str, minutes: float, now: datetime) -> UnlockResult:
        site = self._find_site(site_name)
        if site is None:
            raise ValueError(f"Unknown site: {site_name}")

        if site.override == "block":
            return UnlockResult(granted=False, reason="permanently_blocked")
        if site.override == "allow":
            self.sync(now)
            return UnlockResult(granted=True, reason="granted")

        used = self.ledger.minutes_used_today(site.name, now)
        remaining = site.daily_budget_minutes - used
        if minutes <= 0 or minutes > remaining:
            return UnlockResult(granted=False, reason="insufficient_budget")

        self.ledger.spend_and_unlock(site.name, minutes, now)
        self.sync(now)
        if site.is_blocked(now, self.ledger):
            return UnlockResult(granted=False, reason="still_blocked")
        return UnlockResult(granted=True, reason="granted")

    def lock(self, site_name: str, now: datetime) -> None:
        site = self._find_site(site_name)
        if site is None:
            raise ValueError(f"Unknown site: {site_name}")
        self.ledger.clear_unlock(site.name)
        self.sync(now)

    def daemon(self, interval_seconds: int) -> None:
        while True:
            self.sync(datetime.now())
            time.sleep(interval_seconds)

    def _find_site(self, name: str) -> Site | None:
        return next((s for s in self.sites if s.name == name), None)
