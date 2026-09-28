"""Desire interpretation: real event evidence into Desire Birth / Update.

Pure semantic core of the AA-approved Desire Birth contract (PR #9). It
reads events and world state and returns interpretations; the only writer
of new desire carriers lives at the event-application site in
``engine.core.simulation``.

Contract (Experiment AA, accepted at design level):

- Three discrete evidence prongs decide interpretation. No utility, score,
  threshold, weight, timer, heartbeat, RNG, or event-count trigger is
  involved in birth.
- Prong 1 - executed attempt: ``action_result.status`` in {success, failure}.
- Prong 2 - authored domain map: the canonical action's desire domain
  (union of the production pressure readers and the failure-pressure
  writer), restricted to desires that have an authored birth amount.
  Domains without an authored amount (curiosity) never birth a carrier.
- Prong 3 - observable discrete tie: value / trait / relationship presence
  on the subject. No tie -> no interpretation -> no birth.
"""

from __future__ import annotations

from dataclasses import dataclass

from .action_types import event_action_type
from .models import Consequence

# Explicit sentinel for pre-history: desires that already exist when the
# world clock starts carry GENESIS in source/created_at, never a forged
# runtime event id.
DESIRE_GENESIS = "GENESIS"

# Authored failure-pressure amounts. This was a local map inside
# SimulationEngine._apply_failure_consequences; it is extracted here so the
# failure writer and the desire birth writer share ONE authored source of
# amounts (travel->freedom+8, contact->reconciliation+8/belonging+4,
# help->responsibility+8).
FAILURE_PRESSURE_MAP: dict[str, tuple[tuple[str, float], ...]] = {
    "travel": (("freedom", 8.0),),
    "contact_person": (("reconciliation", 8.0), ("belonging", 4.0)),
    "help_person": (("responsibility", 8.0),),
}

# Authored desire domains of each canonical action type. Documented mirror
# of the production pressure readers (decision.py
# _value_alignment.pressure_by_action and _human_condition_urgency).
# Kept as the source of truth for interpretation; tests assert behavioral
# agreement with those readers.
DESIRE_PRESSURE_MAP: dict[str, tuple[str, ...]] = {
    "travel": ("freedom", "curiosity"),
    "contact_person": ("reconciliation", "belonging"),
    "search_person": ("reconciliation", "belonging"),
    "help_person": ("responsibility",),
}

# Authored birth amounts, flattened from the failure writer's map.
DESIRE_BIRTH_AMOUNT: dict[str, float] = {
    desire: amount
    for entries in FAILURE_PRESSURE_MAP.values()
    for desire, amount in entries
}

# Prong 2: authored domain restricted to authored amounts. Curiosity is
# present in the pressure map but has no authored amount, so it is absent
# here and can never be born (declared gap G4, Experiment AA).
BIRTH_DOMAINS: dict[str, tuple[str, ...]] = {
    action: tuple(desire for desire in desires if desire in DESIRE_BIRTH_AMOUNT)
    for action, desires in DESIRE_PRESSURE_MAP.items()
}


@dataclass(frozen=True)
class DesireInterpretation:
    """One discrete, non-numeric interpretation of an executed event."""

    desire: str
    tie: str
    evidence: str
    amount: float


def _has_value(character, value: str) -> bool:
    return value in character.values


def _tie(character, desire: str, participants: list[str], state) -> str | None:
    """Return the observable discrete tie, or None when nothing is observed.

    This is the answer to "why does THIS character get THIS desire". It is
    existence-only: no magnitude, score, or threshold participates.
    """
    if desire == "freedom":
        if _has_value(character, "freedom"):
            return "value:freedom"
        if "adventurous" in character.traits:
            return "trait:adventurous"
        return None
    if desire == "responsibility":
        if _has_value(character, "responsibility"):
            return "value:responsibility"
        if _has_value(character, "loyalty"):
            return "value:loyalty"
        if any(trait in character.traits for trait in ("compassionate", "protective", "helpful")):
            return "trait:compassionate/protective/helpful"
        return None
    # reconciliation / belonging: an actual relationship with another
    # participant of this event is the observable evidence.
    for other in participants:
        if other == character.id:
            continue
        if state.get_relationship(character.id, other) is not None:
            return f"relationship:{character.id}->{other}"
    return None


def interpret_desire_event(event, state) -> list[DesireInterpretation]:
    """Return the desire interpretations an executed event actually supports.

    Pure: reads the event and world state, mutates nothing, draws no RNG.
    An event with blocked status, no subject, an unknown domain, or no
    observable tie returns ``[]`` and therefore births nothing.
    """
    if event.action_result is None:
        return []
    if event.action_result.status not in ("success", "failure"):
        return []
    if not event.participants:
        return []
    subject = state.characters.get(event.participants[0])
    if subject is None:
        return []
    domains = BIRTH_DOMAINS.get(event_action_type(event), ())
    interpretations: list[DesireInterpretation] = []
    for desire in domains:
        tie = _tie(subject, desire, event.participants, state)
        if tie is None:
            continue
        interpretations.append(
            DesireInterpretation(
                desire=desire,
                tie=tie,
                evidence=event.id,
                amount=DESIRE_BIRTH_AMOUNT[desire],
            )
        )
    return interpretations


def record_satisfaction_evidence(
    state,
    character,
    event,
    desire_name: str,
    old_value: float,
) -> None:
    """Leave causal evidence when a real event actually satisfies a desire.

    Fixes the W gap: satisfaction used to mutate the float with no
    consequence and no provenance. The drop itself becomes an event
    Consequence; when a carrier exists its evidence window records the
    same event. Desires outside the authored carrier vocabulary (curiosity)
    still get the event Consequence but have no carrier to update.
    """
    desires = character.human_condition.desires
    new_value = desires.get(desire_name, old_value)
    if new_value >= old_value:
        # Nothing was satisfied (the value was already floored at zero).
        return
    event.consequences.append(
        Consequence(
            "character",
            character.id,
            f"human_condition.desires.{desire_name}",
            old_value,
            new_value,
            f"event success satisfies {desire_name} pressure",
        )
    )
    carrier = character.desire_carriers.get(desire_name)
    if carrier is None:
        return
    if not carrier.evidence or carrier.evidence[-1] != event.id:
        carrier.evidence.append(event.id)
    carrier.strength = new_value
    carrier.lifecycle = "SATISFIED" if new_value == 0.0 else "WEAKENED"
