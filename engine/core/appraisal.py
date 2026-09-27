"""Typed appraisal + arbitration records for the motivation-interaction layer.

Pure reader of (state, character, pool): no writes to WorldState,
no RNG, no MotivationManager hub. Called once per character per tick,
computes, and is discarded.

Evidence axis: past_event_id + state_delta liveness proxy (count of newer
events that have since rewritten the same relationship pair), NOT a
reason-tag-count. This is the P1-bis-bis-2 / Q2 EvidenceRecord axis,
promoted from /tmp shadow into production use.

Appraisal.interpretation reuses the kernel's OWN DecisionEvaluation.reasons
tags via a read-only evaluate() call (pure re-derivation, no state
mutation — safe exactly as the O/N shadow experiments established).
"""

from __future__ import annotations

from .decision import DecisionKernel
from .action_types import canonical_action_type
from .models import ActionCandidate, AppraisalRecord, ArbitrationResult, EvidenceRecord, WorldState

IMPASSE_GAP = 0.75  # the kernel's EXISTING top-2 utility boundary, reused not redefined


def motivation_source(candidate: ActionCandidate) -> str:
    """Classify which motivation carrier this candidate belongs to, reusing
    the exact vocabulary the M/N/O/P1 experiments already validated."""
    at = "search_person" if candidate.metadata.get("search_target") else canonical_action_type(candidate.action_type)
    md = candidate.metadata or {}
    if md.get("motivation_carrier") == "fulfillment_need":
        return "fulfillment"
    if at == "pursue_goal":
        return "goal"
    if at == "contact_person":
        return "relationship"
    if at == "search_person":
        return "search"
    if at == "travel":
        return "goal"
    if at == "help_person":
        return "compassion"
    if at == "rest":
        return "recovery"
    return "other"


def motivation_salience(character, candidate: ActionCandidate) -> float:
    """The actor's OWN desire-based magnitude for this candidate's motivation
    source. Reuses the same per-action_type desire-name convention the
    kernel's own _human_condition_urgency already uses internally."""
    desires = character.human_condition.desires

    def _d(name: str) -> float:
        return max(0.0, min(100.0, desires.get(name, 0.0))) / 100.0

    src = motivation_source(candidate)
    if src == "fulfillment":
        return 0.5  # same floor used by the M/N/P fulfillment shadow carrier
    if src == "relationship":
        return max(_d("reconciliation"), _d("belonging"))
    if src == "search":
        return max(_d("reconciliation"), _d("belonging"))
    if src == "goal":
        return max(_d("freedom"), _d("curiosity"))
    if src == "compassion":
        return _d("responsibility")
    if src == "recovery":
        return character.human_condition.fatigue / 100.0
    return 0.0


def candidate_focal_target(candidate: ActionCandidate, state: WorldState):
    """Which relationship pair / location does this candidate's outcome
    actually hinge on? Used to find which past events are relevant evidence."""
    md = candidate.metadata or {}
    if md.get("search_target"):
        return ("relationship", candidate.actor_id, md.get("search_target"), "trust")
    if candidate.targets:
        t = candidate.targets[0]
        if canonical_action_type(candidate.action_type) in ("contact_person", "help_person"):
            return ("relationship", candidate.actor_id, t, "trust")
        return ("relationship", candidate.actor_id, t, "trust")
    if candidate.action_type == "travel":
        return ("location", candidate.actor_id, None, None)
    return ("relationship", candidate.actor_id, None, "trust")


def _pair_key(a: str, b: str) -> str:
    return f"{min(a, b)}:{max(a, b)}"


def find_top_evidence(state: WorldState, actor_id: str, focal) -> EvidenceRecord | None:
    """Find the actor's single most-relevant LIVE past event touching the same
    relationship pair as `focal`. Liveness proxy: how many NEWER events have
    since rewritten that same pair — each one partly overwrites this event's
    contribution to the CURRENT relationship value. No hand-tuned relevance
    threshold; the number is derived purely from the recorded event log."""
    actor, target = focal[1], focal[2]
    if target is None:
        return None
    focal_pair = _pair_key(actor, target)
    best: EvidenceRecord | None = None
    best_key: tuple[float, int] | None = None
    for ev in reversed(list(state.event_log)):
        if actor not in ev.participants:
            continue
        other = next((p for p in ev.participants if p != actor), None)
        if other is None or _pair_key(actor, other) != focal_pair:
            continue
        age = state.tick - ev.tick
        newer_writes = sum(
            1
            for e2 in state.event_log
            if e2.tick > ev.tick
            and any(_pair_key(actor, p) == focal_pair for p in e2.participants if p != actor)
        )
        relevance = max(0.0, 1.0 - 0.25 * newer_writes)
        record = EvidenceRecord(
            past_event_id=ev.id,
            state_delta=(focal[0], actor, target),
            motivation_source="",  # filled by caller with the CLAIMING source
            subject_id=actor,
            target_id=target,
            event_age=age,
            current_relevance=relevance,
            interpretation=f"{ev.action_type} at tick {ev.tick} ({ev.location})",
            causal_link=(
                f"{newer_writes} newer event(s) have since rewritten this "
                f"pair's relationship, so this event's contribution to the "
                f"CURRENT state is {'still visible' if newer_writes == 0 else 'partly overwritten'}"
            ),
        )
        key = (record.current_relevance, -record.event_age)
        if best_key is None or key > best_key:
            best, best_key = record, key
    return best


def build_appraisals(
    kernel: DecisionKernel, state: WorldState, character, pool: list[ActionCandidate]
) -> list[AppraisalRecord]:
    """Build one AppraisalRecord per candidate, grounded in the actor's own
    recorded history + the kernel's own per-candidate reasons. Pure function
    of its inputs; no RNG, no state mutation."""
    records: list[AppraisalRecord] = []
    for candidate in pool:
        evaluation = kernel.evaluate(state, candidate)  # read-only re-derivation
        top_evidence = find_top_evidence(state, candidate.actor_id, candidate_focal_target(candidate, state))
        if top_evidence is not None:
            import dataclasses

            top_evidence = dataclasses.replace(top_evidence, motivation_source=motivation_source(candidate))
        records.append(
            AppraisalRecord(
                candidate_id=candidate.id,
                motivation_source=motivation_source(candidate),
                salience=motivation_salience(character, candidate),
                interpretation=tuple(evaluation.reasons),
                evidence=(top_evidence,) if top_evidence is not None else (),
            )
        )
    return records


def arbitrate(
    appraisals: list[AppraisalRecord], pool: list[ActionCandidate], evaluations
) -> ArbitrationResult:
    """Decide RESOLVE / ABSTAIN / INERT for this actor's pool this tick.

    Fires ONLY when:
      (a) the top-2 by utility are within the kernel's existing IMPASSE_GAP, AND
      (b) the top-2 are supported by DIFFERENT motivation sources.
    INERT (either condition false) -> the kernel handles the tick unchanged.
    RESOLVE -> the side with the Distinguishable live EvidenceRecord wins the
      local tie (its record points at a different target, or a different
      still-live event with different relevance).
    ABSTAIN -> neither side has a live, DISTINGUISHING causal reason (both
      lack a live record, or both cite the same undistinguished ground):
      no winner is invented; the caller maps this to an empty pool,
      reaching choose()'s existing None path.
    """
    if len(evaluations) < 2:
        return ArbitrationResult(kind="inert")
    ordered = sorted(evaluations, key=lambda e: e.utility, reverse=True)
    gap = ordered[0].utility - ordered[1].utility
    if gap > IMPASSE_GAP:
        return ArbitrationResult(kind="inert")
    by_id = {a.id: a for a in pool}
    app_by_id = {a.candidate_id: a for a in appraisals}
    top1 = by_id[ordered[0].action_id]
    top2 = by_id[ordered[1].action_id]
    src1, src2 = app_by_id[top1.id].motivation_source, app_by_id[top2.id].motivation_source
    if src1 == src2:
        return ArbitrationResult(kind="inert")

    ev1 = next((e for e in app_by_id[top1.id].evidence if e.current_relevance > 0.5), None)
    ev2 = next((e for e in app_by_id[top2.id].evidence if e.current_relevance > 0.5), None)
    live1, live2 = ev1 is not None, ev2 is not None
    if not live1 and not live2:
        # Neither side has ANY live, auditable causal reason from recorded
        # history: there is nothing for the arbitration layer to weigh
        # against anything else, so it defers back to the kernel's normal
        # mechanic (INERT), NOT a forced quiet. This matches the P1-bis-bis-2
        # B-case definition, which requires BOTH sides to have SOME live
        # evidence that merely fails to distinguish them — not "no evidence
        # at all", which is just an ordinary tick the kernel already handles.
        return ArbitrationResult(kind="inert")
    if live1 and live2:
        distinguishable = (ev1.target_id != ev2.target_id) or (
            ev1.past_event_id != ev2.past_event_id and ev1.current_relevance != ev2.current_relevance
        )
        if distinguishable:
            winner = top1 if (ev1.target_id, ev1.current_relevance) >= (ev2.target_id, ev2.current_relevance) else top2
            return ArbitrationResult(kind="resolve", candidate_id=winner.id, evidence=(ev1, ev2))
        return ArbitrationResult(kind="abstain", evidence=(ev1, ev2))
    if live1 != live2:
        winner = top1 if live1 else top2
        return ArbitrationResult(kind="resolve", candidate_id=winner.id, evidence=(ev1 or ev2,))
    return ArbitrationResult(kind="inert")


def apply_arbitration(pool: list[ActionCandidate], result: ArbitrationResult, evaluations) -> list[ActionCandidate]:
    """Map an ArbitrationResult onto the candidate pool the kernel will see.

    INERT   -> return the pool unchanged.
    RESOLVE -> narrow to the named candidate + its near-tied rival (the other
               top-2 candidate); the kernel still runs its own argmax on
               exactly this 2-candidate set, unchanged mechanics.
    ABSTAIN -> return an EMPTY pool; the kernel's existing empty-pool guard
               (choose(): "if not evaluations: return None, []") then does
               all the mechanical work. No kernel line is added or changed.
    """
    if result.kind == "inert":
        return pool
    if result.kind == "inert" or result.kind not in {"resolve", "abstain"}:
        return pool
    if result.kind == "abstain":
        return []
    winner = next((c for c in pool if c.id == result.candidate_id), None)
    if winner is None:
        return pool
    # Keep the named winner plus its single near-tied rival — the other
    # top-2-by-utility candidate. This is what "narrow to the two
    # candidates actually in tension" means; the winner, by construction
    # of a RESOLVE verdict, is not always the #1-by-utility candidate
    # when salience-based evidence overrides the raw utility ordering.
    top_by_utility = {e.action_id for e in sorted(evaluations, key=lambda e: e.utility, reverse=True)[:2]}
    rival_ids = (top_by_utility - {winner.id}) or top_by_utility
    return [c for c in pool if c.id in {winner.id, *rival_ids}]
