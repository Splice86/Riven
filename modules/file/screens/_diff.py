"""Line-level diffing engine for screen broadcasts.

Computes minimal line-level changes between two snapshots of a file,
returning a structure suitable for WebSocket transmission.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Types
# =============================================================================

@dataclass
class LineDiff:
    """Result of computing a diff between two file versions."""
    path: str
    old_version: int
    new_version: int
    total_lines: int
    sections: list[dict]  # List of changed/added/removed sections


@dataclass
class FileSnapshot:
    """Represents a file at a point in time."""
    path: str
    lines: list[str]
    version: int

    @classmethod
    def from_path(cls, path: str, version: int = 0) -> Optional["FileSnapshot"]:
        """Load a file from disk."""
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            return cls(path=path, lines=lines, version=version)
        except OSError:
            return None

    def slice(self, section: str | None = None, capacity: int = 30) -> list[str]:
        """Get a slice of lines, optionally limited by section and capacity.

        Args:
            section: e.g., "0-30" or "50-100" or None for full file
            capacity: Max lines to return

        Returns:
            List of lines (with newlines stripped)
        """
        if section:
            try:
                start, end = section.split("-")
                lines = self.lines[int(start):int(end)]
            except (ValueError, IndexError):
                lines = self.lines
        else:
            lines = self.lines

        return [line.rstrip("\n\r") for line in lines[:capacity]]


def _compute_diff(
    old_lines: list[str],
    new_lines: list[str],
) -> list[dict]:
    """Compute minimal line-level diff between two file versions.

    Returns a list of section dicts, each describing a changed range.
    Each section: {start, end, action, lines}
      - action: "unchanged" | "changed" | "added" | "removed"
    """
    differ = difflib.SequenceMatcher(None, old_lines, new_lines)
    sections = []

    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == "equal":
            continue  # Skip unchanged regions

        elif tag == "replace":
            # Lines changed: show both old (marked removed) and new (marked added)
            sections.append({
                "action": "removed",
                "start": i1,
                "end": i2,
                "lines": [l.rstrip("\n\r") for l in old_lines[i1:i2]],
            })
            sections.append({
                "action": "added",
                "start": j1,
                "end": j2,
                "lines": [l.rstrip("\n\r") for l in new_lines[j1:j2]],
            })

        elif tag == "delete":
            sections.append({
                "action": "removed",
                "start": i1,
                "end": i2,
                "lines": [l.rstrip("\n\r") for l in old_lines[i1:i2]],
            })

        elif tag == "insert":
            sections.append({
                "action": "added",
                "start": j1,
                "end": j2,
                "lines": [l.rstrip("\n\r") for l in new_lines[j1:j2]],
            })

    return sections


# =============================================================================
# Snapshot store (in-memory, keyed by path)
# =============================================================================

class SnapshotStore:
    """Stores the last-seen version of each file for diff computation."""

    def __init__(self):
        self._snapshots: dict[str, FileSnapshot] = {}

    def update(self, path: str, version: int) -> Optional[FileSnapshot]:
        """Load and store a fresh snapshot of a file."""
        snap = FileSnapshot.from_path(path, version)
        if snap:
            self._snapshots[path] = snap
        return snap

    def get(self, path: str) -> Optional[FileSnapshot]:
        """Get the stored snapshot for a path."""
        return self._snapshots.get(path)

    def compute_diff(self, path: str, old_version: int, new_version: int) -> Optional[LineDiff]:
        """Compute diff between stored snapshot and current disk state.

        Reads fresh from disk each time. Stores the new state so subsequent
        diffs are incremental.
        """
        old_snap = self._snapshots.get(path)
        old_lines = old_snap.lines if old_snap else []
        new_snap = FileSnapshot.from_path(path, new_version)
        if new_snap is None:
            return None

        sections = _compute_diff(old_lines, new_snap.lines)
        self._snapshots[path] = new_snap
        return LineDiff(
            path=path,
            old_version=old_version,
            new_version=new_version,
            total_lines=len(new_snap.lines),
            sections=sections,
        )
