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
