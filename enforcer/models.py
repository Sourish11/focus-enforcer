from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enforcer.ledger import UsageLedger
    from enforcer.rules import BlockRule


@dataclass
class Site:
    name: str
    hostnames: list[str]
    daily_budget_minutes: int
    rules: list["BlockRule"] = field(default_factory=list)

    def is_blocked(self, now: datetime, ledger: "UsageLedger") -> bool:
        return any(rule.is_blocked(self, now, ledger) for rule in self.rules)
