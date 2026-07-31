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


def test_handles_orphaned_managed_start_marker(tmp_path):
    """File with only MANAGED_START (no matching END) should not duplicate markers or drop content."""
    hosts_path = tmp_path / "hosts"
    # Simulate corrupted state: MANAGED_START present but MANAGED_END missing
    # All non-marker lines should be preserved as legitimate content
    hosts_path.write_text("127.0.0.1 localhost\n# FOCUS-ENFORCER-START\n127.0.0.1 old.reddit.com\n")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["youtube.com"])

    content = hosts_path.read_text()
    # Should have exactly one START marker, not two
    assert content.count("# FOCUS-ENFORCER-START") == 1
    assert content.count("# FOCUS-ENFORCER-END") == 1
    # All unrelated lines should be preserved (data loss prevention)
    assert "127.0.0.1 localhost" in content
    assert "127.0.0.1 old.reddit.com" in content
    # New entry should be present
    assert "127.0.0.1 youtube.com" in content


def test_handles_orphaned_managed_end_marker(tmp_path):
    """File with only MANAGED_END (no matching START) should not duplicate markers."""
    hosts_path = tmp_path / "hosts"
    # Simulate corrupted state: MANAGED_END present but MANAGED_START missing
    # Only the orphaned END marker is removed; other content is preserved
    hosts_path.write_text("127.0.0.1 localhost\n# FOCUS-ENFORCER-END\n")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["twitter.com"])

    content = hosts_path.read_text()
    # Should have exactly one pair of markers
    assert content.count("# FOCUS-ENFORCER-START") == 1
    assert content.count("# FOCUS-ENFORCER-END") == 1
    # Old unrelated line should be preserved
    assert "127.0.0.1 localhost" in content
    # New entry should be present
    assert "127.0.0.1 twitter.com" in content


def test_preserves_content_after_orphaned_end_marker(tmp_path):
    """Orphaned END marker should not cause data loss of lines following it."""
    hosts_path = tmp_path / "hosts"
    # Orphaned END marker as first line, with legitimate content after it
    hosts_path.write_text("# FOCUS-ENFORCER-END\n127.0.0.1 mybank.com\n")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com"])

    content = hosts_path.read_text()
    # Should have exactly one pair of markers
    assert content.count("# FOCUS-ENFORCER-START") == 1
    assert content.count("# FOCUS-ENFORCER-END") == 1
    # Legitimate content after orphaned marker must be preserved (data loss prevention)
    assert "127.0.0.1 mybank.com" in content
    # New entry should be present
    assert "127.0.0.1 reddit.com" in content


def test_preserves_content_after_orphaned_start_marker(tmp_path):
    """Orphaned START marker should not cause data loss of lines following it."""
    hosts_path = tmp_path / "hosts"
    # Orphaned START marker with legitimate content after it
    hosts_path.write_text("# FOCUS-ENFORCER-START\n127.0.0.1 mybank.com\n127.0.0.1 localhost\n")
    blocker = HostsFileBlocker(hosts_path)

    blocker.set_blocked_hostnames(["reddit.com"])

    content = hosts_path.read_text()
    # Should have exactly one pair of markers
    assert content.count("# FOCUS-ENFORCER-START") == 1
    assert content.count("# FOCUS-ENFORCER-END") == 1
    # Legitimate content after orphaned marker must be preserved (data loss prevention)
    assert "127.0.0.1 mybank.com" in content
    assert "127.0.0.1 localhost" in content
    # New entry should be present
    assert "127.0.0.1 reddit.com" in content
