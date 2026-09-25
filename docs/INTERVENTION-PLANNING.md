# Intervention Planning

Aetherium now has a structured intervention planning layer:

InterventionRequest -> Impact Analysis -> Conflict Detection -> InterventionPlan

The planner does not mutate authoritative world state.

- Historical rewrites and world-rule changes require a fork.
- Future-only and character-model changes may apply from the current/future boundary after validation.
- Narrative-only changes do not touch world state.
- Conflicts produce a reject plan with explicit findings.

Execution remains separate so every authoritative mutation can pass through checkpoints, branch creation, validation, and event recording.
