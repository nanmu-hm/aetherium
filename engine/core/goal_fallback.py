"""T1 M-B — goal-stagnation actionization (v3 frozen: owner 5957186797 / 5957981558).

M-B lets a character, whose highest-priority staged goal is stuck on a *relational*
stage whose prerequisite is structurally missing, surface a single intermediate
recovery candidate from the EXISTING action space (e.g. ``contact_person`` under
a stuck ``successful_help`` stage). The candidate id carries an ``mb:`` provenance
token so downstream layers can (a) recognize the first real recovery event and
(b) suppress same-form re-generation within the same stagnation instance.

Frozen invariants this module upholds (no exceptions):
- No timers, no tick-based fallback, no attempt/state counters, no random
  injection.
- No ``rest`` fallback, no Store-1 special path.
- The candidate flows through the ordinary
  candidate -> scoring -> decision -> event pipeline (never bypassed).
- The token is a provenance/suppression marker only: it is not a new action
  type, it does not extend the action_type enum, and old events without a
  token keep the old parsing (no backfill, no guessing).
- Location-based stage prerequisites are NOT M-B targets: M-B only actionizes
  relational prerequisites.

T1-1 gate (owner 5964978048 / 5965764446, generation-only reading): M-B fires
ONLY when the current stage has *no generable path* — i.e. the ordinary
candidate pool (generated first, WITHOUT the mb branch) contains NO candidate
whose canonical action_type is in the stage's declared ``action_types``.
Gate decision = pure existence check on the ordinary pool:
  - exists stage-declared candidate in ordinary pool -> M-B stays QUIET
    (the stage has a live generable path through the existing pipeline);
  - otherwise -> M-B may surface its single recovery candidate.
No timer, no counter, no threshold copy, no sorow/RNG proxy, no rest.
"""

from __future__ import annotations

from .action_types import canonical_action_type
from .models import ActionCandidate, CharacterState, WorldState

# Prefix for the provenance token carried in a fallback candidate id.
_T1_TOKEN = "mb"

# Relational stage prerequisites M-B can actionize, mapped to the existing
# action type that works *toward* the prerequisite.
# ``successful_help`` -> ``contact_person`` (NOT ``help_person``): the terminal
# help action requires a distressed target; the intermediate recovery step is to
# contact the target first (an existing, non-distress-gated action).
_RELATIONAL_FALLBACKS: dict[str, str] = {
    "target_same_location": "search_person",
    "successful_contact": "contact_person",
    "successful_help": "contact_person",
}


def _stagnation_goal(character: CharacterState):
    """Highest-priority active staged goal, or None."""
    goal = max(
        (g for g in character.goals if g.status == "active"),
        key=lambda g: g.priority,
        default=None,
    )
    if goal is None or not goal.stage_conditions:
        return None
    if goal.current_stage >= len(goal.stage_conditions):
        return None
    return goal


def _fallback_condition(cond: dict) -> tuple[str, str] | None:
    """Return (recovery_action_type, target_id) for a relational stage
    prerequisite, or None for location-based / non-M-B prerequisites."""
    action_type = _RELATIONAL_FALLBACKS.get(cond.get("type"))
    target = cond.get("target_id")
    if action_type is None or target is None:
        return None
    return action_type, target


def _mb_suppressed(state: WorldState, goal_id: str, stage: int, action_type: str, target_id: str) -> bool:
    """Same-form suppression: True when the event log already holds a
    *successful* ``mb:``-tokened event for the same stagnation instance
    (``goal.id + stage + action_type + target`` all match). Pure structure on
    ``causes[0]`` — no timer, no counter. Old (untokened) events are ignored."""
    prefix = f"{_T1_TOKEN}:{goal_id}:{stage}:{action_type}:{target_id}:"
    for event in state.event_log:
        if event.action_result is None or event.action_result.status != "success":
            continue
        c0 = event.causes[0] if event.causes else ""
        if c0.startswith(prefix):
            return True
    return False


def _stage_generable_in_pool(pool: list, character: CharacterState) -> bool:
    """T1-1 generation-only gate (owner 5965764446 §2): does the current
    stage have a live generable path in the *ordinary* candidate pool?

    The gate reads ONLY the ordinary pool that actions.py has already
    generated (without the mb branch) and checks for the existence of a
    candidate whose canonical action_type is in the current stage's declared
    ``action_types``. This is the minimal executable form of the frozen
    predicate "current stage has no generable path":
      - if such a candidate exists in the ordinary pool -> stage is generable
        -> M-B must stay quiet (no tokened event);
      - if no such candidate -> stage has no generable path -> M-B may fire.

    No timer, no counter, no threshold copy, no utility/score read, no
    sorow/RNG/rest proxy. Pure existence on the ordinary pool.
    """
    goal = _stagnation_goal(character)
    if goal is None:
        return False  # no stage; gate not applicable (M-B returns None anyway)
    stage = goal.current_stage
    cond = goal.stage_conditions[stage]
    declared = set(cond.get("action_types", ()))
    if not declared:
        # Location-only / undeclared action_types: no ordinary pool candidate
        # can match the stage; treat as non-generable (M-B may fire).
        return False
    for cand in pool:
        if cand.id.startswith(_T1_TOKEN + ":"):
            continue  # the mb branch itself is not an ordinary path
        if canonical_action_type(cand.action_type) in declared:
            return True
    return False


def goal_stagnation_candidate(
    state: WorldState,
    character_id: str,
    ordinary_pool: list | None = None,
) -> ActionCandidate | None:
    """The single M-B recovery candidate for a structurally-stuck relational
    stage, tagged with the ``mb:`` provenance token; None otherwise.

    Gate (all must hold — structural only, no timers / counters / RNG):
      1. highest-priority active goal is staged on a relational stage,
      2. that stage's recovery target is present and co-located,
      3. generation-only gate (owner 5965764446 §2): the ordinary pool
         (passed in as ``ordinary_pool``, generated WITHOUT the mb branch)
         has NO candidate whose canonical action_type is in the stage's
         declared ``action_types`` — i.e. the current stage has no
         generable path. If the ordinary pool is None (legacy call), the
         gate is skipped (back-compat for direct tests).
      4. the same-form recovery is not already suppressed by a successful
         ``mb:`` event in the log.
    """
    character = state.characters[character_id]
    goal = _stagnation_goal(character)
    if goal is None:
        return None
    stage = goal.current_stage
    hit = _fallback_condition(goal.stage_conditions[stage])
    if hit is None:
        return None
    action_type, target_id = hit
    target = state.characters.get(target_id)
    if target is None:
        return None
    if target.location != character.location:
        return None
    # T1-1 generation-only gate: the current stage has no generable path in
    # the ordinary pool. If the caller passed the ordinary pool (actions.py),
    # require that no stage-declared candidate exists there; otherwise M-B
    # stays quiet.
    if ordinary_pool is not None and _stage_generable_in_pool(ordinary_pool, character):
        return None
    if _mb_suppressed(state, goal.id, stage, action_type, target_id):
        return None

    base_id = f"tick-{state.tick}-{character.id}-{action_type}"
    token_id = f"{_T1_TOKEN}:{goal.id}:{stage}:{action_type}:{target_id}:{base_id}"
    candidate = ActionCandidate(
        id=token_id,
        actor_id=character.id,
        action_type=action_type,
        targets=[target_id],
        motivation=f"work toward {goal.current_description}",
        preconditions=["target is co-located for the recovery step"],
        expected_outcomes=[f"make progress toward {goal.current_description}"],
        confidence=0.5,
        difficulty=0.0,
        score=0.15,
        metadata={
            "event_action_type": canonical_action_type(action_type),
            "world_validated": True,
            "mb_token": token_id,
        },
    )
    return candidate
