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

M-C (stagnation predicate, owner 5957186797 §(b)): a goal is *structurally
stagnant* when it is the highest-priority active staged goal, its current stage
carries a relational prerequisite, the recovery target is present and co-located,
AND the recovery target has *no* reconciliation desire (a cold, deadlocked
target — the only state that distinguishes a true stagnation from a live
relationship where the target is still reachable/active). That last clause is a
pure read of the target's desire map: no timer, no tick count, no counter.
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


def _target_cold_deadlocked(state: WorldState, target_id: str) -> bool:
    """M-C discriminator: the recovery target is *structurally deadlocked* when
    it has NO reconciliation desire in its desire map. A target that still
    carries a reconciliation desire is part of a live (reachable/active)
    relationship, not a stagnation, so M-B must stay quiet. Pure read of the
    target's desire map — no timer, no tick, no counter. Read-only."""
    target = state.characters.get(target_id)
    if target is None:
        return False
    recon = target.human_condition.desires.get("reconciliation")
    # None (absent) is the cold-deadlock state; a present value (even 0.0)
    # means the desire carrier exists => the relationship is not dead.
    return recon is None


def goal_stagnation_candidate(state: WorldState, character_id: str) -> ActionCandidate | None:
    """The single M-B recovery candidate for a structurally-stuck relational
    stage, tagged with the ``mb:`` provenance token; None otherwise.

    Gate (all must hold — structural only, no timers / counters / RNG):
      1. highest-priority active goal is staged on a relational stage,
      2. that stage's recovery target is present, co-located, and cold
         (no reconciliation desire — a truly deadlocked target),
      3. the same-form recovery is not already suppressed by a successful
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
    if not _target_cold_deadlocked(state, target_id):
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
