from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from enforcer.ledger import UsageLedger
    from enforcer.rules import BlockRule

# "allow"  = permanently unblocked (bypasses budget/schedule)
# "block"  = permanently blocked (unlock will not work)
# None     = normal budget/schedule rules
Override = Literal["allow", "block"] | None


@dataclass
class Site:
    name: str
    hostnames: list[str]
    daily_budget_minutes: int
    rules: list["BlockRule"] = field(default_factory=list)
    override: Override = None

    def is_blocked(self, now: datetime, ledger: "UsageLedger") -> bool:
        if self.override == "allow":
            return False
        if self.override == "block":
            return True
        return any(rule.is_blocked(self, now, ledger) for rule in self.rules)
