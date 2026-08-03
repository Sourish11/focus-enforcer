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

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
mkdir -p ~/.config/focus-enforcer
cp config.example.yaml ~/.config/focus-enforcer/config.yaml
# edit ~/.config/focus-enforcer/config.yaml to list your own sites
```

Editing `/etc/hosts` requires root, so `unlock` and `daemon` must run
with `sudo`. Two things to watch out for:

- `enforcer` only exists inside the venv (`venv/bin/enforcer`), and
  `sudo` resets `PATH`, so `sudo enforcer ...` fails with "command not
  found." Use the full path under `venv/bin/`.
- `sudo` also resets `HOME` (usually to `/root`), and this tool's
  default config/state paths use `Path.home()`. Without `-E`, sudo
  commands would use `/root/.config/focus-enforcer/...` instead of your
  user's. Pass `-E` so both agree on the same paths.

```bash
sudo -E venv/bin/enforcer status
sudo -E venv/bin/enforcer unlock reddit --minutes 15
sudo -E venv/bin/enforcer daemon   # run in the foreground, or wrap in a systemd user service
```

(`status` doesn't need root — `venv/bin/enforcer status` is fine.)

## Running the tests

```bash
venv/bin/python3 -m pytest -v
```
