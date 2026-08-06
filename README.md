# Focus Enforcer

A website-blocking tool for Linux that enforces a daily time budget per
site (via `/etc/hosts`), plus optional fixed-hours blocking — e.g. block
YouTube outright 9am-5pm, and cap Reddit at 20 minutes/day the rest of
the time.

Built for CS3003 (Programming Languages). The main OOP piece is an
abstract `BlockRule` base class with `BudgetRule` and `ScheduleRule`
subclasses. A `Site` just asks each of its rules whether it's blocked —
so adding a new rule type later doesn't require changing `Site` or
`FocusEnforcer`.

Inspired by the daily-allowance idea in a separate personal project,
[`blockinator`](https://github.com/Sourish11/blockinator) (an iOS/Android
Instagram Reels/Explore blocker). This is a separate from-scratch
implementation for desktop Linux websites; no code is shared.

## Ideas in one minute

- **Configured sites are blocked by default** (written into `/etc/hosts`).
- **Budget** = how many minutes you may unlock that site today.
- **Unlock** = spend some of today's budget to allow access for N minutes.
- **Schedule** = hard block during a time window (wins even if budget remains).
- **Block** = permanently blocked (budget unlock will not work).
- **Unblock** = permanently allowed (bypass budget and schedule).
- **Reset** = clear permanent block/unblock; normal rules apply again.
- Changes that affect blocking **sync `/etc/hosts` automatically**
  (you'll see `Synced hosts automatically.`).

**Note:** Sync writes ``/etc/hosts`` and also installs an ``nftables`` rule that
drops outbound traffic to the site's resolved IPs. That means blocking still
works when a browser uses DNS-over-HTTPS and ignores ``/etc/hosts``.

## Setup (once)

```bash
cd ~/projects/focus-enforcer
python -m venv venv

# activate the venv
source venv/bin/activate          # bash / zsh
# source venv/bin/activate.fish   # fish

pip install -e ".[dev]"
mkdir -p ~/.config/focus-enforcer
cp config.example.yaml ~/.config/focus-enforcer/config.yaml
```

You can edit that YAML by hand, or manage sites entirely from the
terminal (recommended).

### sudo notes

Commands that change `/etc/hosts` need root. Always use:

```bash
sudo -E venv/bin/enforcer ...
```

- Use the **full path** `venv/bin/enforcer` (sudo clears `PATH`).
- Pass **`-E`** so config/state stay under your home, not `/root`.
- Optional: run `sudo -v` once so you are not prompted mid-demo.

## Easiest way: interactive menu

```bash
cd ~/projects/focus-enforcer
sudo -v
python scripts/demo_menu.py
```

The menu clears after each action. Type a key, follow the prompts,
press Enter to return.

| Key | What it does |
|-----|----------------|
| `1` | Status — table of state, budget, schedule, hosts |
| `2` | Use budget — temporary allow (spend minutes) |
| `3` | Add a site |
| `4` | Remove a site |
| `5` | Change daily budget |
| `6` | Set or clear hard-block schedule |
| `7` | Permanently block |
| `8` | Permanently unblock |
| `9` | Reset — clear permanent override; normal rules |
| `q` | Quit |

Typical first run:

1. `1` — see Reddit/YouTube from the example config  
2. `2` — use budget for Reddit (5 minutes)  
3. `1` — confirm Reddit is unlocked  
4. `7` — permanently block Reddit  
5. `9` — reset Reddit to normal rules  

## CLI (same features, no menu)

```bash
# Inspect (no sudo)
venv/bin/enforcer status

# Manage sites
sudo -E venv/bin/enforcer add twitter --hostnames twitter.com,www.twitter.com --budget 15
sudo -E venv/bin/enforcer set-budget twitter --minutes 20
sudo -E venv/bin/enforcer set-schedule youtube --start 09:00 --end 17:00
sudo -E venv/bin/enforcer set-schedule youtube --clear
sudo -E venv/bin/enforcer remove twitter

# Block / unlock
sudo -E venv/bin/enforcer unlock reddit --minutes 15
sudo -E venv/bin/enforcer block reddit
sudo -E venv/bin/enforcer unblock youtube
sudo -E venv/bin/enforcer reset youtube

# Optional: keep re-applying when unlock windows expire
sudo -E venv/bin/enforcer daemon
```

(`status` does not need root.)

## Running the tests

```bash
venv/bin/python3 -m pytest -v
```
