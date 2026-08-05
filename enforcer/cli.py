from __future__ import annotations

import argparse
import os
import pwd
from datetime import datetime, time
from pathlib import Path

import yaml

from enforcer.config import Config, build_site, load_config, save_config, site_schedule
from enforcer.enforcer import FocusEnforcer
from enforcer.hosts_blocker import HostsFileBlocker
from enforcer.ledger import UsageLedger
from enforcer.models import Override, Site
from enforcer.network_blocker import NftNetworkBlocker

DEFAULT_HOSTS_PATH = Path("/etc/hosts")


def _default_home() -> Path:
    """Home directory for config/state — even when running under sudo.

    ``Path.home()`` follows the effective uid (/root under sudo), which would
    read/write a different config than the invoking user. Prefer SUDO_USER.
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    home = os.environ.get("HOME")
    if home:
        return Path(home)
    return Path.home()


def _default_config_path() -> Path:
    return _default_home() / ".config" / "focus-enforcer" / "config.yaml"


def _default_state_path() -> Path:
    return _default_home() / ".local" / "state" / "focus-enforcer" / "state.json"


def _ensure_invoking_user_owns(path: Path) -> None:
    """If we wrote files as root via sudo, chown them back to the real user."""
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or not path.exists():
        return
    try:
        pw = pwd.getpwnam(sudo_user)
    except KeyError:
        return
    try:
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except OSError:
        return


def _save_config(config_path: Path, config: Config) -> None:
    save_config(config_path, config)
    _ensure_invoking_user_owns(config_path)


def _build_enforcer(state_path: Path, hosts_path: Path, config_path: Path) -> tuple[FocusEnforcer, Config]:
    config = load_config(config_path)
    ledger = UsageLedger(state_path)
    blocker = HostsFileBlocker(hosts_path)
    return (
        FocusEnforcer(
            sites=config.sites,
            ledger=ledger,
            blocker=blocker,
            network_blocker=NftNetworkBlocker(),
        ),
        config,
    )


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _find_site_index(config: Config, name: str) -> int | None:
    for i, site in enumerate(config.sites):
        if site.name == name:
            return i
    return None


def _rebuild_keeping(
    site: Site,
    *,
    daily_budget_minutes: int | None = None,
    schedule_start: time | None = None,
    schedule_end: time | None = None,
    clear_schedule: bool = False,
    override: Override | object = ...,
) -> Site:
    schedule = site_schedule(site)
    if clear_schedule:
        start = None
        end = None
    elif schedule_start is not None and schedule_end is not None:
        start = schedule_start
        end = schedule_end
    elif schedule is not None:
        start = schedule.start
        end = schedule.end
    else:
        start = None
        end = None

    new_override: Override = site.override if override is ... else override  # type: ignore[assignment]

    return build_site(
        name=site.name,
        hostnames=site.hostnames,
        daily_budget_minutes=site.daily_budget_minutes
        if daily_budget_minutes is None
        else daily_budget_minutes,
        schedule_start=start,
        schedule_end=end,
        override=new_override,
    )


def _flush_dns_caches() -> None:
    import subprocess

    for cmd in (
        ["resolvectl", "flush-caches"],
        ["systemd-resolve", "--flush-caches"],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True)
            return
        except OSError:
            continue


def _try_sync(enforcer: FocusEnforcer, now: datetime) -> int | None:
    try:
        enforcer.sync(now)
    except PermissionError:
        print("Permission denied writing to hosts file — re-run with sudo.")
        return 1
    blocked = sorted(enforcer.blocker.managed_hostnames())
    print("Synced hosts automatically.")
    if blocked:
        print("Currently in /etc/hosts: " + ", ".join(blocked))
    else:
        print("Currently in /etc/hosts: (none)")
    print("Firewall IP block updated (works even if the browser ignores /etc/hosts).")
    _flush_dns_caches()
    return None


def _hosts_marker(site: Site, managed: set[str]) -> str:
    if not site.hostnames:
        return "n/a"
    present = [h in managed for h in site.hostnames]
    if all(present):
        return "yes"
    if any(present):
        return "partial"
    return "no"


def _cmd_status(enforcer: FocusEnforcer, now: datetime) -> int:
    if not enforcer.sites:
        print("No sites configured.")
        return 0

    managed = enforcer.blocker.managed_hostnames()
    headers = ("SITE", "STATE", "IN HOSTS", "BUDGET LEFT", "SCHEDULE", "HOSTS")
    rows: list[tuple[str, str, str, str, str, str]] = []
    for site in enforcer.sites:
        used = enforcer.ledger.minutes_used_today(site.name, now)
        remaining = max(0.0, site.daily_budget_minutes - used)
        schedule = site_schedule(site)
        if site.override == "allow":
            state = "unblocked*"
        elif site.override == "block":
            state = "blocked*"
        else:
            state = "blocked" if site.is_blocked(now, enforcer.ledger) else "unlocked"
        schedule_text = (
            f"{schedule.start.strftime('%H:%M')}-{schedule.end.strftime('%H:%M')}"
            if schedule is not None
            else "none"
        )
        rows.append(
            (
                site.name,
                state,
                _hosts_marker(site, managed),
                f"{remaining:.0f}/{site.daily_budget_minutes} min",
                schedule_text,
                ", ".join(site.hostnames),
            )
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells: tuple[str, ...] | list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    rule = "-+-".join("-" * w for w in widths)
    print(fmt(headers))
    print(rule)
    for row in rows:
        print(fmt(row))
    if any(site.override is not None for site in enforcer.sites):
        print()
        print("* permanent override — use `reset` to return to normal budget/schedule rules")
    print()
    print("IN HOSTS = whether /etc/hosts currently redirects that site to localhost.")
    print("Blocking also drops traffic by IP in the firewall (bypasses browser DNS tricks).")
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
        elif result.reason == "permanently_blocked":
            print(f"{site_name} is permanently blocked — run: enforcer reset {site_name}")
        else:
            print(
                f"{site_name} is still blocked by a scheduled block window, "
                "even though budget was spent"
            )
            print("Synced hosts automatically.")
        return 1
    site = next(s for s in enforcer.sites if s.name == site_name)
    if site.override == "allow":
        print(f"{site_name} is already permanently unblocked")
    else:
        print(f"Unlocked {site_name} for {minutes} minutes")
    print("Synced hosts automatically.")
    return 0


def _cmd_set_override(
    config: Config,
    config_path: Path,
    enforcer: FocusEnforcer,
    name: str,
    override: Override,
    now: datetime,
) -> int:
    idx = _find_site_index(config, name)
    if idx is None:
        print(f"Unknown site: {name}")
        return 1
    site = config.sites[idx]
    config.sites[idx] = _rebuild_keeping(site, override=override)
    _save_config(config_path, config)
    enforcer.sites = config.sites
    if override in (None, "block"):
        enforcer.ledger.clear_unlock(name)
    if override == "allow":
        print(f"Permanently unblocked {name} (bypasses budget and schedule)")
    elif override == "block":
        print(f"Permanently blocked {name} (unlock will not work until you reset)")
    else:
        print(f"Reset {name} — normal budget/schedule rules apply again")
    _ensure_invoking_user_owns(config_path)
    _ensure_invoking_user_owns(enforcer.ledger.state_path)
    err = _try_sync(enforcer, now)
    if err is not None:
        print("(Config was saved, but hosts were not updated — re-run with sudo.)")
        return err
    return 0


def _cmd_add(
    config: Config,
    config_path: Path,
    enforcer: FocusEnforcer,
    name: str,
    hostnames: list[str],
    budget: int,
    schedule_start: time | None,
    schedule_end: time | None,
    now: datetime,
) -> int:
    if _find_site_index(config, name) is not None:
        print(f"Site already exists: {name}")
        return 1
    if not hostnames:
        print("At least one hostname is required")
        return 1
    if budget < 0:
        print("Budget must be >= 0")
        return 1
    site = build_site(
        name=name,
        hostnames=hostnames,
        daily_budget_minutes=budget,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
    )
    config.sites.append(site)
    _save_config(config_path, config)
    enforcer.sites = config.sites
    print(f"Added {name}")
    err = _try_sync(enforcer, now)
    if err is not None:
        print("(Config was saved, but hosts were not updated — re-run with sudo.)")
        return err
    return 0


def _cmd_remove(
    config: Config,
    config_path: Path,
    enforcer: FocusEnforcer,
    name: str,
    now: datetime,
) -> int:
    idx = _find_site_index(config, name)
    if idx is None:
        print(f"Unknown site: {name}")
        return 1
    config.sites.pop(idx)
    _save_config(config_path, config)
    enforcer.sites = config.sites
    print(f"Removed {name}")
    err = _try_sync(enforcer, now)
    if err is not None:
        print("(Config was saved, but hosts were not updated — re-run with sudo.)")
        return err
    return 0


def _cmd_set_budget(
    config: Config,
    config_path: Path,
    enforcer: FocusEnforcer,
    name: str,
    budget: int,
    now: datetime,
) -> int:
    idx = _find_site_index(config, name)
    if idx is None:
        print(f"Unknown site: {name}")
        return 1
    if budget < 0:
        print("Budget must be >= 0")
        return 1
    site = config.sites[idx]
    config.sites[idx] = _rebuild_keeping(site, daily_budget_minutes=budget)
    _save_config(config_path, config)
    enforcer.sites = config.sites
    print(f"Set budget for {name} to {budget} minutes")
    err = _try_sync(enforcer, now)
    if err is not None:
        print("(Config was saved, but hosts were not updated — re-run with sudo.)")
        return err
    return 0


def _cmd_set_schedule(
    config: Config,
    config_path: Path,
    enforcer: FocusEnforcer,
    name: str,
    start: time | None,
    end: time | None,
    clear: bool,
    now: datetime,
) -> int:
    idx = _find_site_index(config, name)
    if idx is None:
        print(f"Unknown site: {name}")
        return 1
    site = config.sites[idx]
    if clear:
        config.sites[idx] = _rebuild_keeping(site, clear_schedule=True)
        print(f"Cleared schedule for {name}")
    else:
        assert start is not None and end is not None
        config.sites[idx] = _rebuild_keeping(site, schedule_start=start, schedule_end=end)
        print(f"Set schedule for {name} to {start.strftime('%H:%M')}-{end.strftime('%H:%M')}")
    _save_config(config_path, config)
    enforcer.sites = config.sites
    err = _try_sync(enforcer, now)
    if err is not None:
        print("(Config was saved, but hosts were not updated — re-run with sudo.)")
        return err
    return 0


def main(
    argv: list[str] | None = None,
    state_path: Path | None = None,
    hosts_path: Path | None = None,
    config_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="enforcer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show live state, budget, hosts, and schedule")

    unlock_parser = subparsers.add_parser("unlock", help="Spend budget to temporarily unlock a site")
    unlock_parser.add_argument("site")
    unlock_parser.add_argument("--minutes", type=float, required=True)

    block_parser = subparsers.add_parser(
        "block",
        help="Permanently block a site (unlock will not work until reset)",
    )
    block_parser.add_argument("site")

    unblock_parser = subparsers.add_parser(
        "unblock",
        help="Permanently unblock a site (bypasses budget and schedule until reset)",
    )
    unblock_parser.add_argument("site")

    reset_parser = subparsers.add_parser(
        "reset",
        help="Clear permanent block/unblock; return to normal budget/schedule rules",
    )
    reset_parser.add_argument("site")

    add_parser = subparsers.add_parser("add", help="Add a site to the config")
    add_parser.add_argument("name")
    add_parser.add_argument(
        "--hostnames",
        required=True,
        help="Comma-separated hostnames (e.g. reddit.com,www.reddit.com)",
    )
    add_parser.add_argument("--budget", type=int, required=True, help="Daily budget in minutes")
    add_parser.add_argument("--schedule-start", default=None, help="Optional schedule start HH:MM")
    add_parser.add_argument("--schedule-end", default=None, help="Optional schedule end HH:MM")

    remove_parser = subparsers.add_parser("remove", help="Remove a site from the config")
    remove_parser.add_argument("name")

    set_budget_parser = subparsers.add_parser("set-budget", help="Change a site's daily budget")
    set_budget_parser.add_argument("site")
    set_budget_parser.add_argument("--minutes", type=int, required=True)

    set_schedule_parser = subparsers.add_parser(
        "set-schedule",
        help="Set or clear a hard block schedule window",
    )
    set_schedule_parser.add_argument("site")
    set_schedule_parser.add_argument("--start", default=None, help="HH:MM")
    set_schedule_parser.add_argument("--end", default=None, help="HH:MM")
    set_schedule_parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove the schedule window",
    )

    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Background loop: re-apply blocks when unlock windows expire",
    )
    daemon_parser.add_argument("--interval-seconds", type=int, default=None)

    args = parser.parse_args(argv)

    resolved_config_path = config_path or _default_config_path()
    resolved_state_path = state_path or _default_state_path()
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
        if args.command == "block":
            return _cmd_set_override(
                config, resolved_config_path, enforcer, args.site, "block", now
            )
        if args.command == "unblock":
            return _cmd_set_override(
                config, resolved_config_path, enforcer, args.site, "allow", now
            )
        if args.command == "reset":
            return _cmd_set_override(
                config, resolved_config_path, enforcer, args.site, None, now
            )
        if args.command == "add":
            if (args.schedule_start is None) != (args.schedule_end is None):
                print("Provide both --schedule-start and --schedule-end, or neither")
                return 1
            start = _parse_hhmm(args.schedule_start) if args.schedule_start else None
            end = _parse_hhmm(args.schedule_end) if args.schedule_end else None
            hostnames = [h.strip() for h in args.hostnames.split(",") if h.strip()]
            return _cmd_add(
                config,
                resolved_config_path,
                enforcer,
                args.name,
                hostnames,
                args.budget,
                start,
                end,
                now,
            )
        if args.command == "remove":
            return _cmd_remove(config, resolved_config_path, enforcer, args.name, now)
        if args.command == "set-budget":
            return _cmd_set_budget(
                config, resolved_config_path, enforcer, args.site, args.minutes, now
            )
        if args.command == "set-schedule":
            if args.clear:
                return _cmd_set_schedule(
                    config, resolved_config_path, enforcer, args.site, None, None, True, now
                )
            if args.start is None or args.end is None:
                print("Provide --start and --end, or use --clear")
                return 1
            return _cmd_set_schedule(
                config,
                resolved_config_path,
                enforcer,
                args.site,
                _parse_hhmm(args.start),
                _parse_hhmm(args.end),
                False,
                now,
            )
        if args.command == "daemon":
            interval = args.interval_seconds or config.enforcement_interval_seconds
            enforcer.daemon(interval)
            return 0
    except ValueError as exc:
        print(f"Invalid time: {exc}")
        return 1
    except PermissionError:
        print(f"Permission denied writing to {resolved_hosts_path} — re-run with sudo.")
        return 1

    return 1
