from __future__ import annotations

import ipaddress
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol


class NetworkBlocker(Protocol):
    def set_blocked_hostnames(self, hostnames: list[str]) -> None: ...


class NullNetworkBlocker:
    """No-op network blocker for tests / hosts-only mode."""

    def set_blocked_hostnames(self, hostnames: list[str]) -> None:
        return None


class NftNetworkBlocker:
    """Drop outbound traffic to resolved IPs of blocked hostnames via nftables.

    Browsers with DNS-over-HTTPS bypass ``/etc/hosts``. Blocking the destination
    IPs at the firewall still stops the connection.
    """

    TABLE = "focus_enforcer"
    RESOLVER = "https://cloudflare-dns.com/dns-query"

    def set_blocked_hostnames(self, hostnames: list[str]) -> None:
        ipv4: set[str] = set()
        ipv6: set[str] = set()
        for hostname in hostnames:
            for addr in self._resolve(hostname):
                try:
                    parsed = ipaddress.ip_address(addr)
                except ValueError:
                    continue
                if parsed.version == 4:
                    ipv4.add(str(parsed))
                else:
                    ipv6.add(str(parsed))
        self._apply(ipv4, ipv6)

    def _resolve(self, hostname: str) -> list[str]:
        addrs: list[str] = []
        for record_type in ("A", "AAAA"):
            addrs.extend(self._dns_query(hostname, record_type))
        return addrs

    def _dns_query(self, hostname: str, record_type: str) -> list[str]:
        query = urllib.parse.urlencode({"name": hostname, "type": record_type})
        request = urllib.request.Request(
            f"{self.RESOLVER}?{query}",
            headers={"accept": "application/dns-json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return []
        answers = payload.get("Answer") or []
        return [item["data"] for item in answers if item.get("data") and item.get("type") in {1, 28}]

    def _apply(self, ipv4: set[str], ipv6: set[str]) -> None:
        # Replace any previous table so unlock/unblock always converge.
        subprocess.run(
            ["nft", "delete", "table", "inet", self.TABLE],
            check=False,
            capture_output=True,
        )
        if not ipv4 and not ipv6:
            return

        lines = [f"table inet {self.TABLE} {{"]
        if ipv4:
            elements = ", ".join(sorted(ipv4))
            lines.extend(
                [
                    "  set blocked4 {",
                    "    type ipv4_addr",
                    f"    elements = {{ {elements} }}",
                    "  }",
                ]
            )
        if ipv6:
            elements = ", ".join(sorted(ipv6))
            lines.extend(
                [
                    "  set blocked6 {",
                    "    type ipv6_addr",
                    f"    elements = {{ {elements} }}",
                    "  }",
                ]
            )
        lines.append("  chain output {")
        lines.append("    type filter hook output priority filter; policy accept;")
        if ipv4:
            lines.append("    ip daddr @blocked4 drop")
        if ipv6:
            lines.append("    ip6 daddr @blocked6 drop")
        lines.append("  }")
        lines.append("}")
        result = subprocess.run(
            ["nft", "-f", "-"],
            input="\n".join(lines) + "\n",
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "nft failed").strip()
            raise PermissionError(detail)
