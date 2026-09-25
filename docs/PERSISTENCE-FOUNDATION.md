# Persistence and Agency Foundation

The persistence layer makes authoritative history recoverable and inspectable.

Pipeline:

Simulation Event -> JSON Event Store
                 -> Canon Ledger
                 -> Checkpoint Snapshot
                 -> Branch / Fork / Rollback
                 -> Deterministic Replay Verification

The JSON snapshot is versioned. Event storage is append-only JSONL. Canon entries carry provenance fields instead of hiding origin inside prompts.

Branches preserve a checkpoint at their fork point. Rollback loads an earlier checkpoint; it does not erase the old event log.

Replay verification reruns the deterministic simulation from an initial snapshot and compares authoritative event signatures.
