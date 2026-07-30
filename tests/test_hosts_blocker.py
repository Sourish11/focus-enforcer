from enforcer.hosts_blocker import HostsFileBlocker


def test_adds_managed_block_to_empty_file(tmp_path):
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com", "old.reddit.com"])

    content = hosts_path.read_text()
    assert "# FOCUS-ENFORCER-START" in content
    assert "127.0.0.1 reddit.com" in content
    assert "127.0.0.1 old.reddit.com" in content
    assert "# FOCUS-ENFORCER-END" in content


def test_preserves_existing_unrelated_lines(tmp_path):
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("127.0.0.1 localhost\n::1 localhost\n")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com"])

    content = hosts_path.read_text()
    assert "127.0.0.1 localhost" in content
    assert "::1 localhost" in content
    assert "127.0.0.1 reddit.com" in content


def test_second_call_replaces_managed_block_without_duplicating(tmp_path):
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com"])
    blocker.set_blocked_hostnames(["youtube.com"])

    content = hosts_path.read_text()
    assert content.count("# FOCUS-ENFORCER-START") == 1
    assert "127.0.0.1 reddit.com" not in content
    assert "127.0.0.1 youtube.com" in content


def test_empty_hostname_list_clears_managed_entries(tmp_path):
    hosts_path = tmp_path / "hosts"
    hosts_path.write_text("")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com"])
    blocker.set_blocked_hostnames([])

    content = hosts_path.read_text()
    assert "127.0.0.1 reddit.com" not in content
    assert "# FOCUS-ENFORCER-START" in content
    assert "# FOCUS-ENFORCER-END" in content
