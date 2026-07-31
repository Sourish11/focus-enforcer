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
        managed = (
            [self.MANAGED_START]
            + [f"127.0.0.1 {hostname}" for hostname in hostnames]
            + [self.MANAGED_END]
        )
        self._write_lines(before + managed + after)

    def _read_lines(self) -> list[str]:
        if not self.hosts_path.exists():
            return []
        return self.hosts_path.read_text().splitlines()

    def _write_lines(self, lines: list[str]) -> None:
        self.hosts_path.write_text("\n".join(lines) + "\n")

    def _split_managed(self, lines: list[str]) -> tuple[list[str], list[str]]:
        has_start = self.MANAGED_START in lines
        has_end = self.MANAGED_END in lines

        # Both markers present: normal case
        if has_start and has_end:
            start_idx = lines.index(self.MANAGED_START)
            end_idx = lines.index(self.MANAGED_END)
            return lines[:start_idx], lines[end_idx + 1 :]

        # Only START present: strip only the START marker itself, preserve content before and after
        if has_start and not has_end:
            start_idx = lines.index(self.MANAGED_START)
            return lines[:start_idx], lines[start_idx + 1 :]

        # Only END present: strip only the orphaned END marker itself, preserve content before and after
        if has_end and not has_start:
            end_idx = lines.index(self.MANAGED_END)
            return lines[:end_idx], lines[end_idx + 1 :]

        # Neither marker present: no managed block to remove
        return lines, []
