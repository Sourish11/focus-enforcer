from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from enforcer.config import Config, load_config
from enforcer.enforcer import FocusEnforcer
from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "focus-enforcer" / "config.yaml"
DEFAULT_STATE_PATH = Path.home() / ".local" / "state" / "focus-enforcer" / "state.json"
DEFAULT_HOSTS_PATH = Path("/etc/hosts")


def _build_enforcer(state_path: Path, hosts_path: Path, config_path: Path) -> tuple[FocusEnforcer, Config]:
    config = load_config(config_path)
    ledger = UsageLedger(state_path)
    blocker = HostsFileBlocker(hosts_path)
    return FocusEnforcer(sites=config.sites, ledger=ledger, blocker=blocker), config


def _cmd_status(enforcer: FocusEnforcer, now: datetime) -> int:
    for site in enforcer.sites:
        used = enforcer.ledger.minutes_used_today(site.name, now)
        remaining = max(0.0, site.daily_budget_minutes - used)
        state = "blocked" if site.is_blocked(now, enforcer.ledger) else "unlocked"
        print(f"{site.name}: {state} ({remaining:.0f} of {site.daily_budget_minutes} min remaining today)")
    return 0


def _cmd_unlock(enforcer: FocusEnforcer, site_name: str, minutes: float, now: datetime) -> int:
    try:
        result = enforcer.unlock(site_name, minutes, now)
    except ValueError:
        print(f"Unknown site: {site_name}")
        return 1
    if not result.granted:
        if result.reason == "insufficient_budget":
            print(f"No budget remaining today for {site_name}")
        else:
            # Budget was spent, but the site is still blocked by another rule
            # (e.g. a ScheduleRule covering a fixed work-hours window).
            print(f"{site_name} is still blocked by a scheduled block window, even though budget was spent")
        return 1
    print(f"Unlocked {site_name} for {minutes} minutes")
    return 0


def main(
    argv: list[str] | None = None,
    state_path: Path | None = None,
    hosts_path: Path | None = None,
    config_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="enforcer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    unlock_parser = subparsers.add_parser("unlock")
    unlock_parser.add_argument("site")
    unlock_parser.add_argument("--minutes", type=float, required=True)

    daemon_parser = subparsers.add_parser("daemon")
    daemon_parser.add_argument("--interval-seconds", type=int, default=None)

    args = parser.parse_args(argv)

    resolved_config_path = config_path or DEFAULT_CONFIG_PATH
    resolved_state_path = state_path or DEFAULT_STATE_PATH
    resolved_hosts_path = hosts_path or DEFAULT_HOSTS_PATH

    try:
        enforcer, config = _build_enforcer(resolved_state_path, resolved_hosts_path, resolved_config_path)
    except FileNotFoundError:
        print(f"Config file not found: {resolved_config_path}")
        return 1
    except yaml.YAMLError:
        print(f"Config file is not valid YAML: {resolved_config_path}")
        return 1
    except (KeyError, TypeError):
        print(f"Config file is missing required fields: {resolved_config_path}")
        return 1

    now = datetime.now()

    try:
        if args.command == "status":
            return _cmd_status(enforcer, now)
        if args.command == "unlock":
            return _cmd_unlock(enforcer, args.site, args.minutes, now)
        if args.command == "daemon":
            interval = args.interval_seconds or config.enforcement_interval_seconds
            enforcer.daemon(interval)
            return 0
    except PermissionError:
        print(f"Permission denied writing to {resolved_hosts_path} — re-run with sudo.")
        return 1
