from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CanonEntry:
    id: str
    statement: str
    entry_type: str
    source_id: str
    branch_id: str = "main"
    tick: int = 0
    status: str = "active"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Checkpoint:
    id: str
    branch_id: str
    tick: int
    timestamp: str
    snapshot_file: str
    reason: str = ""


@dataclass
class BranchRecord:
    id: str
    parent_branch_id: str | None
    fork_tick: int
    checkpoint_id: str
    reason: str = ""
    created_by: str = "system"
    status: str = "active"
