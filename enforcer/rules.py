from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enforcer.ledger import UsageLedger
    from enforcer.models import Site


class BlockRule(ABC):
    @abstractmethod
    def is_blocked(self, site: "Site", now: datetime, ledger: "UsageLedger") -> bool:
        raise NotImplementedError


class BudgetRule(BlockRule):
    """Blocked unless the site currently has an active unlock window."""

    def is_blocked(self, site: "Site", now: datetime, ledger: "UsageLedger") -> bool:
        return not ledger.is_currently_unlocked(site.name, now)


class ScheduleRule(BlockRule):
    """Blocked whenever `now`'s time-of-day falls in [start, end), regardless of budget."""

    def __init__(self, start: time, end: time):
        self.start = start
        self.end = end

    def is_blocked(self, site: "Site", now: datetime, ledger: "UsageLedger") -> bool:
        return self.start <= now.time() < self.end
