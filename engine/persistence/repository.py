from __future__ import annotations

import hashlib
from pathlib import Path

from ..core.models import WorldState
from .codec import load_world_json, save_world_json
from .models import BranchRecord, Checkpoint


class WorldRepository:
    """Minimal filesystem repository for snapshots, event logs, canon, and branches."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.snapshots = self.root / "snapshots"
        self.branches = self.root / "branches"
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self.branches.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _snapshot_id(state: WorldState, branch_id: str) -> str:
        return f"{branch_id}-tick-{state.tick}"

    def save_checkpoint(self, state: WorldState, branch_id: str, reason: str = "") -> Checkpoint:
        checkpoint_id = self._snapshot_id(state, branch_id)
        filename = self.snapshots / f"{checkpoint_id}.json"
        save_world_json(state, filename)
        return Checkpoint(
            id=checkpoint_id,
            branch_id=branch_id,
            tick=state.tick,
            timestamp=state.timestamp,
            snapshot_file=str(filename),
            reason=reason,
        )

    def load_checkpoint(self, checkpoint: Checkpoint) -> WorldState:
        return load_world_json(checkpoint.snapshot_file)

    def create_branch(
        self,
        state: WorldState,
        parent_branch_id: str | None,
        branch_id: str,
        reason: str,
        created_by: str = "system",
    ) -> BranchRecord:
        checkpoint = self.save_checkpoint(state, branch_id, reason=reason)
        record = BranchRecord(
            id=branch_id,
            parent_branch_id=parent_branch_id,
            fork_tick=state.tick,
            checkpoint_id=checkpoint.id,
            reason=reason,
            created_by=created_by,
        )
        (self.branches / f"{branch_id}.json").write_text(
            __import__("json").dumps(record.__dict__, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return record

    def load_branch(self, branch_id: str) -> BranchRecord:
        import json
        path = self.branches / f"{branch_id}.json"
        return BranchRecord(**json.loads(path.read_text(encoding="utf-8")))

    def fork(self, state: WorldState, branch_id: str, reason: str, created_by: str = "user") -> WorldState:
        record = self.create_branch(state, state.active_branch, branch_id, reason, created_by)
        child = self.load_checkpoint(self.load_checkpoint_record(record))
        child.active_branch = branch_id
        return child

    def load_checkpoint_record(self, record: BranchRecord) -> Checkpoint:
        checkpoint_path = self.snapshots / f"{record.checkpoint_id}.json"
        from .models import Checkpoint
        world = load_world_json(checkpoint_path)
        return Checkpoint(record.checkpoint_id, record.id, world.tick, world.timestamp, str(checkpoint_path), record.reason)

    def rollback(self, checkpoint: Checkpoint) -> WorldState:
        state = load_world_json(checkpoint.snapshot_file)
        state.active_branch = checkpoint.branch_id
        return state

    def snapshot_hash(self, state: WorldState) -> str:
        import json
        payload = json.dumps(
            save_payload(state),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def save_payload(state: WorldState) -> dict:
    from .codec import world_to_dict
    return world_to_dict(state)
