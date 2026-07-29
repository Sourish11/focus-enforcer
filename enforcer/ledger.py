from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


class UsageLedger:
    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._state = self._load()

    def _load(self) -> dict:
        if not self.state_path.exists():
            return {"usage": {}, "unlocked_until": {}}
        return json.loads(self.state_path.read_text())

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self._state))

    @staticmethod
    def _day_key(now: datetime) -> str:
        return now.strftime("%Y-%m-%d")

    def minutes_used_today(self, site_name: str, now: datetime) -> float:
        day = self._state["usage"].get(self._day_key(now), {})
        return day.get(site_name, 0.0)

    def is_currently_unlocked(self, site_name: str, now: datetime) -> bool:
        until_iso = self._state["unlocked_until"].get(site_name)
        if until_iso is None:
            return False
        return now < datetime.fromisoformat(until_iso)

    def spend_and_unlock(self, site_name: str, minutes: float, now: datetime) -> None:
        day = self._state["usage"].setdefault(self._day_key(now), {})
        day[site_name] = day.get(site_name, 0.0) + minutes
        until = now + timedelta(minutes=minutes)
        self._state["unlocked_until"][site_name] = until.isoformat()
        self._save()
