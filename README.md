# Focus Enforcer

A website-blocking tool for Linux that enforces a daily time budget per
site (via `/etc/hosts`), plus optional fixed-hours blocking — e.g. block
YouTube outright 9am-5pm, and cap Reddit at 20 minutes/day the rest of
the time.

Built for CS3003 (Programming Languages), demonstrating the
**object-oriented paradigm**: an abstract `BlockRule` base class with two
concrete subclasses (`BudgetRule`, `ScheduleRule`), and a `Site` that
polymorphically asks each of its rules "am I blocked?" without knowing or
caring which rule types it holds. Adding a new kind of rule later (e.g. a
`WeekendOnlyRule`) requires zero changes to `Site` or `FocusEnforcer` —
that's the practical payoff of the polymorphic design.

Inspired by the daily-allowance idea in a separate personal project,
[`blockinator`](https://github.com/Sourish11/blockinator) (an iOS/Android
Instagram Reels/Explore blocker) — this is an independent, from-scratch
implementation for a different platform and domain (desktop website
blocking, not app-screen blocking); no code is shared between the two.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p ~/.config/focus-enforcer
cp config.example.yaml ~/.config/focus-enforcer/config.yaml
# edit ~/.config/focus-enforcer/config.yaml to list your own sites
```

Editing `/etc/hosts` requires root, so `unlock` and `daemon` must run
with `sudo`:

```bash
sudo enforcer status
sudo enforcer unlock reddit --minutes 15
sudo enforcer daemon   # run in the foreground, or wrap in a systemd user service
```

## Running the tests

```bash
pytest -v
```

## Design

See `docs/design.md` for the
full design writeup, including the OOP class breakdown and rationale.
