from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from enforcer.config import load_config
from enforcer.enforcer import FocusEnforcer
from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "focus-enforcer" / "config.yaml"
DEFAULT_STATE_PATH = Path.home() / ".local" / "state" / "focus-enforcer" / "state.json"
DEFAULT_HOSTS_PATH = Path("/etc/hosts")


def _build_enforcer(state_path: Path, hosts_path: Path, config_path: Path) -> FocusEnforcer:
    config = load_config(config_path)
    ledger = UsageLedger(state_path)
    blocker = HostsFileBlocker(hosts_path)
    return FocusEnforcer(sites=config.sites, ledger=ledger, blocker=blocker)


def _cmd_status(enforcer: FocusEnforcer, now: datetime) -> int:
    for site in enforcer.sites:
        used = enforcer.ledger.minutes_used_today(site.name, now)
        remaining = max(0.0, site.daily_budget_minutes - used)
        state = "blocked" if site.is_blocked(now, enforcer.ledger) else "unlocked"
        print(f"{site.name}: {state} ({remaining:.0f} of {site.daily_budget_minutes} min remaining today)")
    return 0


def _cmd_unlock(enforcer: FocusEnforcer, site_name: str, minutes: float, now: datetime) -> int:
    # Determine, before spending anything, whether this request would fail
    # purely for lack of budget — so the failure message below is accurate
    # even though `unlock()` itself may already have spent the budget (in
    # the "still blocked by another rule" case).
    site = next((s for s in enforcer.sites if s.name == site_name), None)
    insufficient_budget = True
    if site is not None:
        used = enforcer.ledger.minutes_used_today(site.name, now)
        remaining = site.daily_budget_minutes - used
        insufficient_budget = minutes <= 0 or minutes > remaining

    try:
        granted = enforcer.unlock(site_name, minutes, now)
    except ValueError:
        print(f"Unknown site: {site_name}")
        return 1
    if not granted:
        if insufficient_budget:
            print(f"No budget remaining today for {site_name}")
        else:
            # Budget was spent, but the site is still blocked by another rule
            # (e.g. a ScheduleRule covering a fixed work-hours window).
            print(f"{site_name} is still blocked by a scheduled block window, even though budget was spent")
        return 1
    print(f"Unlocked {site_name} for {minutes} minutes")
    return 0


def _cmd_daemon(enforcer: FocusEnforcer, interval_seconds: int) -> int:
    enforcer.daemon(interval_seconds)
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
        enforcer = _build_enforcer(resolved_state_path, resolved_hosts_path, resolved_config_path)
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
            config = load_config(resolved_config_path)
            interval = args.interval_seconds or config.enforcement_interval_seconds
            return _cmd_daemon(enforcer, interval)
    except PermissionError:
        print(f"Permission denied writing to {resolved_hosts_path} — re-run with sudo.")
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2
