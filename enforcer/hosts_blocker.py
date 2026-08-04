from __future__ import annotations

from pathlib import Path


class HostsFileBlocker:
    MANAGED_START = "# FOCUS-ENFORCER-START"
    MANAGED_END = "# FOCUS-ENFORCER-END"

    def __init__(self, hosts_path: Path):
        self.hosts_path = Path(hosts_path)

    def set_blocked_hostnames(self, hostnames: list[str]) -> None:
        lines = self._read_lines()
        before, after = self._split_managed(lines)
        managed = [self.MANAGED_START]
        for hostname in hostnames:
            # Block both IPv4 and IPv6 — many browsers prefer AAAA and
            # would otherwise bypass a 127.0.0.1-only hosts entry.
            managed.append(f"127.0.0.1 {hostname}")
            managed.append(f"::1 {hostname}")
        managed.append(self.MANAGED_END)
        new_lines = before + managed + after
        if new_lines != lines:
            self._write_lines(new_lines)

    def managed_hostnames(self) -> set[str]:
        """Hostnames currently listed in the managed block (either address family)."""
        lines = self._read_lines()
        before, after = self._split_managed(lines)
        # Everything between markers is dropped by _split_managed; re-read the gap.
        has_start = self.MANAGED_START in lines
        has_end = self.MANAGED_END in lines
        if not has_start or not has_end:
            return set()
        start = lines.index(self.MANAGED_START)
        end = lines.index(self.MANAGED_END)
        found: set[str] = set()
        for line in lines[start + 1 : end]:
            parts = line.split()
            if len(parts) >= 2 and parts[0] in {"127.0.0.1", "::1"}:
                found.add(parts[1])
        return found

    def _read_lines(self) -> list[str]:
        if not self.hosts_path.exists():
            return []
        return self.hosts_path.read_text().splitlines()

    def _write_lines(self, lines: list[str]) -> None:
        self.hosts_path.write_text("\n".join(lines) + "\n")

    def _split_managed(self, lines: list[str]) -> tuple[list[str], list[str]]:
        has_start = self.MANAGED_START in lines
        has_end = self.MANAGED_END in lines

        # Neither marker present: no managed block to remove
        if not has_start and not has_end:
            return lines, []

        # Whichever marker is missing (orphaned start/end), fall back to the
        # marker that is present so only that single marker line is stripped.
        before_idx = lines.index(self.MANAGED_START) if has_start else lines.index(self.MANAGED_END)
        after_idx = lines.index(self.MANAGED_END) if has_end else lines.index(self.MANAGED_START)
        return lines[:before_idx], lines[after_idx + 1 :]
