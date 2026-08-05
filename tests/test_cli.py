from pathlib import Path

from enforcer.cli import main


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sites:
  - name: reddit
    hostnames: [reddit.com]
    daily_budget_minutes: 20
enforcement_interval_seconds: 30
"""
    )
    return config_path


def _state_and_hosts_paths(tmp_path: Path) -> tuple[Path, Path]:
    state_path = tmp_path / "state.json"
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("")
    return state_path, hosts_path


def test_status_reports_blocked_site_by_default(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "reddit" in out
    assert "blocked" in out.lower()
    assert "reddit.com" in out
    assert "20 min" in out
    assert "SITE" in out
    assert "STATE" in out


def test_unlock_then_status_reports_unlocked(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["unlock", "reddit", "--minutes", "5"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0

    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    out = capsys.readouterr().out
    assert "unlocked" in out.lower()


def test_unlock_refused_reports_error(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    main(
        ["unlock", "reddit", "--minutes", "20"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    capsys.readouterr()

    exit_code = main(
        ["unlock", "reddit", "--minutes", "5"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "no budget remaining" in out.lower()


def test_unlock_unknown_site_reports_error(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["unlock", "nonexistent", "--minutes", "5"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "unknown site" in out.lower()


def test_missing_config_file_reports_error(tmp_path, capsys):
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)
    missing_config = tmp_path / "does-not-exist.yaml"

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=missing_config,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "config" in out.lower()


def test_invalid_config_yaml_reports_error(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("sites: [this is not: valid: yaml: at all")
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "config" in out.lower()


def test_config_missing_sites_key_reports_error(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("enforcement_interval_seconds: 30\n")
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "config" in out.lower()


def test_config_site_missing_daily_budget_minutes_reports_error(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
sites:
  - name: reddit
    hostnames: [reddit.com]
"""
    )
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "config" in out.lower()


def test_unwritable_hosts_file_reports_error(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)
    hosts_path.chmod(0o444)

    try:
        exit_code = main(
            ["unlock", "reddit", "--minutes", "5"],
            state_path=state_path,
            hosts_path=hosts_path,
            config_path=config_path,
        )
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "permission" in out.lower() or "sudo" in out.lower()
    finally:
        hosts_path.chmod(0o644)


def test_add_site_shows_in_status(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["add", "twitter", "--hostnames", "twitter.com,www.twitter.com", "--budget", "15"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0

    exit_code = main(
        ["status"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "twitter" in out
    assert "15 min" in out


def test_add_duplicate_site_fails(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["add", "reddit", "--hostnames", "reddit.com", "--budget", "10"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 1
    assert "already exists" in capsys.readouterr().out.lower()


def test_remove_site(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["remove", "reddit"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0

    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    out = capsys.readouterr().out
    assert "No sites configured" in out


def test_set_budget(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["set-budget", "reddit", "--minutes", "40"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0

    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    assert "40 min" in capsys.readouterr().out


def test_set_and_clear_schedule(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["set-schedule", "reddit", "--start", "09:00", "--end", "17:00"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    assert "09:00-17:00" in capsys.readouterr().out

    exit_code = main(
        ["set-schedule", "reddit", "--clear"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    assert "none" in capsys.readouterr().out


def test_block_after_unlock(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    main(
        ["unlock", "reddit", "--minutes", "5"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    assert "unlocked" in capsys.readouterr().out.lower()

    exit_code = main(
        ["block", "reddit"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    out = capsys.readouterr().out.lower()
    assert "blocked*" in out or "blocked *" in out or "blocked*" in out.replace(" ", "")
    assert "127.0.0.1 reddit.com" in hosts_path.read_text()

    exit_code = main(
        ["unlock", "reddit", "--minutes", "5"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 1
    assert "permanently blocked" in capsys.readouterr().out.lower()


def test_permanent_unblock_then_reset(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["unblock", "reddit"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    assert "127.0.0.1 reddit.com" not in hosts_path.read_text()

    main(["status"], state_path=state_path, hosts_path=hosts_path, config_path=config_path)
    assert "unblocked" in capsys.readouterr().out.lower()

    exit_code = main(
        ["reset", "reddit"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    assert "127.0.0.1 reddit.com" in hosts_path.read_text()
    assert "Reset reddit" in capsys.readouterr().out


def test_default_home_uses_sudo_user(monkeypatch):
    import pwd
    from enforcer import cli

    class FakePw:
        pw_dir = "/home/alice"

    monkeypatch.setenv("SUDO_USER", "alice")
    monkeypatch.setenv("HOME", "/root")
    monkeypatch.setattr(cli.pwd, "getpwnam", lambda name: FakePw())
    assert cli._default_home() == Path("/home/alice")
    assert cli._default_config_path() == Path("/home/alice/.config/focus-enforcer/config.yaml")


def test_add_syncs_hosts(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    state_path, hosts_path = _state_and_hosts_paths(tmp_path)

    exit_code = main(
        ["add", "twitter", "--hostnames", "twitter.com", "--budget", "10"],
        state_path=state_path,
        hosts_path=hosts_path,
        config_path=config_path,
    )
    assert exit_code == 0
    content = hosts_path.read_text()
    assert "127.0.0.1 reddit.com" in content
    assert "127.0.0.1 twitter.com" in content
    assert "Synced hosts automatically." in capsys.readouterr().out
