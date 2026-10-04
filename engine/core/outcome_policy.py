"""Make rest's always-succeed an explicit action-policy authority, and make
its fact generation status-sensitive.

ChatGPT 5979725052 (re-ruling; supersedes 5979580831 which authorised (a)).
Branch m-b-goal-directed-ab. Tests first, no merge.

SCOPE, exactly as authorised
    A. keep eligible rest => success, but raise it from an implicit overwrite
       to an EXPLICIT, locatable, testable action-policy authority
    B. restore status-sensitive facts at simulation.py:772
    C. mechanical acceptance (nine items, listed in the report)

EXPLICITLY OUT OF SCOPE, untouched
    * the rest eligibility gate (actions.py:268)
    * every other action
    * causal-ledger, T1, T2, 8c5a8fd, 12c9276
    * search_person and the world_validated probability pinning
    * the inherited appraisal_regression failure

WHY A DECLARATION AND NOT A COMMENT
The old code asserted the outcome inside the per-action branch, after the
resolver had already rolled. That has two defects the ruling names: the
authority is not locatable, and the flow is pseudo -- it rolls a random outcome
and then discards it. A declaration at module level fixes the first. Consulting
it BEFORE the resolver fixes the second, and it also means the discarded RNG
draw disappears rather than being spent on a result nobody uses.
"""
from __future__ import annotations

from collections.abc import Callable

from engine.core.models import ActionCandidate, ActionResult, WorldState

# --- Explicit action outcome policies ---------------------------------------
#
# An action named here OWNS its final committed outcome. The resolver is not
# consulted for it, and no result is discarded. This mapping IS the authority:
# it is locatable by name, it is testable without touching production
# behaviour, and an action that is absent from it has no override at all.
#
# rest
#   3ad2b21 "Make goal progress and pressure state-driven" recorded the rule in
#   prose at the point of introduction:
#
#       "Rest is a non-contestable biological/social action in this model: if
#        it is available, it succeeds rather than rolling against an arbitrary
#        success probability."
#
#   That is a business policy about rest, not an accident of implementation, and
#   the commit replaced a failure-aware branch to install it. What was lost is
#   not the policy but its declaration: a later edit dropped the comment and
#   kept the assignment, leaving an authority with no locatable form.
#
#   This restores the declaration. The semantics are unchanged: a rest action
#   that has passed its preconditions commits success with reason
#   "rest completed" and probability 1.0.
ACTION_OUTCOME_POLICIES: dict[str, Callable[[], ActionResult]] = {
    "rest": lambda: ActionResult("success", "rest completed", 1.0),
}


def resolve_policy_outcome(action: ActionCandidate) -> ActionResult | None:
    """Return the declared outcome for `action`, or None if it has no policy.

    None means "this action has no authority of its own", which is the normal
    case: the resolver's result stands and is committed unchanged.
    """
    factory = ACTION_OUTCOME_POLICIES.get(action.action_type)
    return factory() if factory is not None else None


def policy_actions() -> list[str]:
    """The action types that hold declared outcome authority, sorted."""
    return sorted(ACTION_OUTCOME_POLICIES)
