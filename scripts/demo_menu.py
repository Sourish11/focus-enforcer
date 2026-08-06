#!/usr/bin/env python3
"""Interactive terminal menu for the FocusForce product surface.

Run from the project root (with venv created)::

    python scripts/demo_menu.py

Tip: run ``sudo -v`` once before starting so host-changing commands don't stall.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENFORCER = ROOT / "venv" / "bin" / "enforcer"

MENU = r"""
            +========================================================================+
            |                                                                        |
            |                            .-=[!@$#@$%]=-.                             |
            |                           //             \\                            |
            |                          ||   .-------.   ||                           |
            |                          ||  /  .---.  \  ||                           |
            |                          || |  (  *  )  | ||                           |
            |                          ||  \  '---'  /  ||                           |
            |                          ||   '-------'   ||                           |
            |                           \\             //                            |
            |                            '-=[@!$%#@$]=-'                             |
            |                                                                        |
            |                 ---->>>  F O C U S F O R C E  <<<----                  |
            |                                                                        |
            +========================================================================+
            |  HOW TO USE                                                            |
            |    Type a number and press Enter.                                      |
            |    Sites are blocked by default. Use budget spends daily minutes.      |
            |    Schedule = hard block during hours (even if budget remains).        |
            |    Block / Unblock = permanent overrides. Reset = back to normal.      |
            |    Enforcement uses /etc/hosts AND a firewall IP drop (no DoH needed). |
            |    Run `sudo -v` once first if commands ask for a password.            |
            +========================================================================+
            |                                                                        |
            |    --- daily ---                                                       |
            |    1)  Status           table of state, budget, schedule, hosts        |
            |    2)  Use budget       temporary allow (spends budget minutes)        |
            |                                                                        |
            |    --- manage sites ---                                                |
            |    3)  Add site         start managing a new website                   |
            |    4)  Remove site      stop managing a website                        |
            |    5)  Set budget       change daily minutes for a site                |
            |    6)  Set schedule     hard-block window (or clear it)                |
            |    7)  Block site       permanently block (no budget unlock)           |
            |    8)  Unblock site     permanently allow (bypass budget/schedule)     |
            |    9)  Reset site       clear permanent override; normal rules         |
            |                                                                        |
            |    q)  Quit                                                            |
            |                                                                        |
            +========================================================================+
"""


def _clear() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")


def _pause() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except (EOFError, KeyboardInterrupt):
        print()


def _run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=ROOT)
    _pause()
    return result.returncode


def _ask(prompt: str) -> str:
    return input(prompt).strip()


def _sudo_enforcer(enforcer: str, *args: str) -> list[str]:
    return ["sudo", "-E", enforcer, *args]


def main() -> int:
    if not ENFORCER.is_file():
        print(f"enforcer not found at {ENFORCER}")
        print("Create the venv and install first:")
        print("  python -m venv venv")
        print("  source venv/bin/activate          # bash")
        print("  source venv/bin/activate.fish     # fish")
        print("  pip install -e .")
        return 1

    enforcer = str(ENFORCER)

    while True:
        _clear()
        print(MENU)
        try:
            choice = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in {"q", "quit", "exit"}:
            _clear()
            print("Done.")
            return 0
        if choice == "1":
            _run([enforcer, "status"])
        elif choice == "2":
            print("\nSpend budget minutes for temporary access")
            site = _ask("Site name: ")
            minutes = _ask("Minutes to use: ")
            _run(_sudo_enforcer(enforcer, "unlock", site, "--minutes", minutes))
        elif choice == "3":
            print("\nAdd a site to block (example name: twitter)")
            name = _ask("Site name: ")
            hostnames = _ask("Hostnames (comma-separated, e.g. twitter.com,www.twitter.com): ")
            budget = _ask("Daily budget minutes (e.g. 15): ")
            start = _ask("Schedule start HH:MM (blank to skip): ")
            end = _ask("Schedule end HH:MM (blank to skip): ")
            cmd = _sudo_enforcer(
                enforcer,
                "add",
                name,
                "--hostnames",
                hostnames,
                "--budget",
                budget,
            )
            if start and end:
                cmd.extend(["--schedule-start", start, "--schedule-end", end])
            _run(cmd)
        elif choice == "4":
            name = _ask("\nSite name to remove: ")
            _run(_sudo_enforcer(enforcer, "remove", name))
        elif choice == "5":
            site = _ask("\nSite name: ")
            minutes = _ask("New daily budget minutes: ")
            _run(_sudo_enforcer(enforcer, "set-budget", site, "--minutes", minutes))
        elif choice == "6":
            print("\nHard-block during a daily window, or clear an existing schedule")
            site = _ask("Site name: ")
            clear = _ask("Clear schedule instead? (y/N): ").lower()
            if clear in {"y", "yes"}:
                _run(_sudo_enforcer(enforcer, "set-schedule", site, "--clear"))
            else:
                start = _ask("Schedule start HH:MM: ")
                end = _ask("Schedule end HH:MM: ")
                _run(
                    _sudo_enforcer(
                        enforcer,
                        "set-schedule",
                        site,
                        "--start",
                        start,
                        "--end",
                        end,
                    )
                )
        elif choice == "7":
            print("\nPermanently block (use budget will not work until you Reset)")
            site = _ask("Site name: ")
            _run(_sudo_enforcer(enforcer, "block", site))
        elif choice == "8":
            print("\nPermanently unblock (bypasses budget/schedule until you Reset)")
            site = _ask("Site name: ")
            _run(_sudo_enforcer(enforcer, "unblock", site))
        elif choice == "9":
            print("\nClear permanent block/unblock; normal budget/schedule rules apply again")
            site = _ask("Site name: ")
            _run(_sudo_enforcer(enforcer, "reset", site))
        else:
            print("Pick 1-9 or q.")
            _pause()


if __name__ == "__main__":
    sys.exit(main())
