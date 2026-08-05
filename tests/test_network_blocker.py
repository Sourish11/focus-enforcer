import json
from enforcer.network_blocker import NftNetworkBlocker, NullNetworkBlocker


def test_null_network_blocker_is_noop():
    NullNetworkBlocker().set_blocked_hostnames(["youtube.com"])


def test_nft_network_blocker_builds_rules(monkeypatch):
    blocker = NftNetworkBlocker()
    calls: list[list[str]] = []

    def fake_dns(hostname: str, record_type: str):
        if record_type == "A":
            return ["203.0.113.10"]
        return ["2001:db8::10"]

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        class Result:
            returncode = 0
            stderr = ""
            stdout = ""
        if cmd[:3] == ["nft", "-f", "-"]:
            # keep the rendered ruleset for assertions
            calls[-1] = ["nft", "-f", "-", kwargs.get("input", "")]
        return Result()

    monkeypatch.setattr(blocker, "_dns_query", fake_dns)
    monkeypatch.setattr("enforcer.network_blocker.subprocess.run", fake_run)

    blocker.set_blocked_hostnames(["youtube.com"])

    assert any(c[:3] == ["nft", "delete", "table"] for c in calls)
    rendered = next(c[3] for c in calls if c[:3] == ["nft", "-f", "-"])
    assert "203.0.113.10" in rendered
    assert "2001:db8::10" in rendered
    assert "ip daddr @blocked4 drop" in rendered
    assert "ip6 daddr @blocked6 drop" in rendered


def test_nft_network_blocker_clears_table_when_empty(monkeypatch):
    blocker = NftNetworkBlocker()
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        class Result:
            returncode = 0
            stderr = ""
            stdout = ""
        return Result()

    monkeypatch.setattr("enforcer.network_blocker.subprocess.run", fake_run)
    blocker.set_blocked_hostnames([])
    assert calls and calls[0][:4] == ["nft", "delete", "table", "inet"]
    assert not any(c[:2] == ["nft", "-f"] for c in calls)
