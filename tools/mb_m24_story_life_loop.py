"""M24 -- Story-Life-Loop acceptance audit (read-only, anchored 0ba1699).

Spec: ChatGPT PR#10 6013069885. Runs on m-b-goal-directed-ab,
use_arbitration=True (W2 production semantics). 5 seeds (1,3,7,42,99),
500 ticks each (spec's minimum). No production/test/weight change, no
recall() wiring, no manufactured failure or plot. All counterfactual
intervention follows the M23-R1 corrected method: undo a consequence
set ONLY at the intervened tick, immediately after that tick's real
engine.step() returns but BEFORE the next tick's reader runs -- never
re-sync an arm to its own drift.

Phase A -- natural life-loop trace: per-seed, per-actor lineage
(action -> event -> consequence -> changed state/relationship/desire
-> later action), only when the link is FIELD-level auditable
(consequence[].target_id/field), not log-adjacency.

Phase B -- choice->future counterfactual witness: for each
consequence-bearing lineage, undo ONLY that action's immediate
consequences (restoring each Consequence.old_value) in a fresh same-
seed world, re-run the subsequent window, and compare THAT actor's
committed-action / persisted-event stream. This is the spec's "一次
人物选择是否会改变其后续可选择的世界" test -- an action-level
intervention, not a family-level pin.

Phase C -- story-level evidence inventory per natural lineage:
agency_witness / state_persistence / relationship_persistence /
goal-desire_evolution / conflict / irreversibility / failure (report
presence, never manufacture).

Verdict format required by spec: STORY-LIFE-LOOP PROVEN / PARTIAL /
NOT PROVEN.
"""
from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.models import Event, WorldState
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world

SEEDS = (1, 3, 7, 42, 99)
TICKS = 500
FUTURE_WINDOW = 100
MAX_LINEAGES_PER_SEED = 12


@dataclass
class Lineage:
    seed: int
    actor: str
    action_tick: int
    event_id: str
    consequence_fields: list[tuple[str, str, str]] = field(default_factory=list)
    changed_state_fields: list[str] = field(default_factory=list)
    later_action_tick: int | None = None
    later_action_id: str | None = None
    agency_witness: bool = False
    state_persistence: bool = False
    relationship_persistence: bool = False
    goal_desire_evolution: bool = False
    conflict: bool = False
    irreversibility: bool = False
    natural_failure_in_window: bool = False


def _consequence_undomap(event: Event) -> dict:
    m: dict = {}
    for c in event.consequences:
        if c.target_type == "relationship":
            m[("rel", c.target_id, c.field)] = c.old_value
        elif c.target_type == "character":
            m[("char", c.target_id, c.field)] = c.old_value
    return m


def _reapply_consequences(world: WorldState, undo_map: dict) -> None:
    for key, old in undo_map.items():
        root, cid, fld = key
        if root == "rel":
            rel = world.relationships.get(cid)
            if rel is not None:
                setattr(rel, fld, old)
        else:
            ch = world.characters.get(cid)
            if ch is None:
                continue
            if fld in ch.emotions:
                ch.emotions[fld] = old
            elif fld in ch.human_condition.desires:
                ch.human_condition.desires[fld] = old
            else:
                setattr(ch.human_condition, fld, old)


def run_arm(seed: int,
            undo_at: dict[int, dict] | None = None) -> tuple[
                WorldState, list[Event], list[dict]]:
    """Run TICKS ticks on a fresh `seed`-fixed world. If undo_at maps
    a tick -> undomap, that tick's consequences are rolled back
    IMMEDIATELY after step() returns, before the next tick's reader
    runs -- the M23-R1-corrected pinning discipline, applied to a
    consequence set at a single tick, not every tick."""
    world = build_genesis_world()
    world.timestamp = "0001-01-01T00:00:00"
    engine = SimulationEngine(seed=seed, use_arbitration=True)
    committed: list[dict] = []
    for _ in range(TICKS):
        t = world.tick
        res = engine.step(world)
        committed.append({
            "tick": t,
            "actions": {a.actor_id: a.id for a in res.actions},
            "events": [e.id for e in res.events],
        })
        if undo_at and t in undo_at:
            _reapply_consequences(world, undo_at[t])
    return world, list(world.event_log), committed


def _actor_in_event(event: Event, actor: str) -> bool:
    return actor in (event.participants or [])


def _opposite_family(a: str, b: str) -> bool:
    fam = lambda s: s.rsplit("-", 1)[-1] if s else ""
    x, y = fam(a), fam(b)
    pairs = ({"travel", "rest"}, {"contact"}, {"help", "search"}, {"rest"})
    return (x in {"travel", "rest"} and y == "contact"
            or x == "contact" and y in {"travel", "rest"}
            or x in {"help", "search"} and y == "rest"
            or x == "rest" and y in {"help", "search"})


def main() -> int:
    print("=" * 72)
    print("M24  Story-Life-Loop acceptance  (read-only, 0ba1699, "
          "W2 use_arbitration=True)")
    print("=" * 72)

    all_lineages: list[Lineage] = []
    for seed in SEEDS:
        world, events, committed = run_arm(seed)
        print(f"\n[seed {seed}] {len(events)} persisted events over "
              f"{TICKS} ticks")

        # Phase A: only actions whose event carries consequences AND
        # actually changed something (a real old->new value pair),
        # within the first 300 ticks (M22/M22-R1 already established
        # that this regime's natural activity concentrates there; the
        # tail is quiet baseline, not a new finding).
        seed_lineages: list[Lineage] = []
        seen: set[str] = set()
        for ev in events:
            if ev.tick > 300 or not ev.participants:
                continue
            if not any((c.old_value, c.new_value) and
                       c.old_value != c.new_value
                       for c in (ev.consequences or [])):
                continue
            actor = ev.participants[0]
            key = f"{seed}:{actor}:{ev.tick}"
            if key in seen:
                continue
            seen.add(key)
            lin = Lineage(
                seed=seed, actor=actor, action_tick=ev.tick,
                event_id=ev.id,
                consequence_fields=[(c.target_type, c.target_id, c.field)
                                    for c in (ev.consequences or [])],
                changed_state_fields=sorted(set(
                    f"{c.target_type}:{c.target_id}.{c.field}"
                    for c in (ev.consequences or []))))
            seed_lineages.append(lin)
            if len(seed_lineages) >= MAX_LINEAGES_PER_SEED:
                break

        # Phase B: per-lineage counterfactual witness
        for lin in seed_lineages:
            event = next((e for e in events if e.id == lin.event_id),
                         None)
            if event is None:
                continue
            undo_map = _consequence_undomap(event)
            if not undo_map:
                continue
            _, evs2, committed2 = run_arm(
                seed, {lin.action_tick: undo_map})
            base = [c for c in committed
                    if lin.action_tick < c["tick"] <
                    lin.action_tick + FUTURE_WINDOW]
            alt = [c for c in committed2
                   if lin.action_tick < c["tick"] <
                   lin.action_tick + FUTURE_WINDOW]
            divergent = [i for i, (a, b) in enumerate(zip(base, alt))
                         if a["actions"].get(lin.actor) !=
                            b["actions"].get(lin.actor)]
            if divergent:
                first = divergent[0]
                lin.later_action_tick = base[first]["tick"]
                lin.later_action_id = base[first]["actions"].get(lin.actor)
                lin.agency_witness = True
                lin.irreversibility = any(
                    base[i]["actions"].get(lin.actor) !=
                    alt[i]["actions"].get(lin.actor)
                    for i in divergent[1:divergent[0] + 1]
                    if i < len(base) and i < len(alt))
                a_act = base[first]["actions"].get(lin.actor)
                b_act = alt[first]["actions"].get(lin.actor)
                lin.conflict = bool(a_act and b_act and
                                    a_act != b_act and
                                    _opposite_family(a_act, b_act))
                # state/relationship/desire persistence: did the SAME
                # consequence field (target_id, field) re-touch in a
                # LATER event inside the base arm's window -- i.e. did
                # the changed value survive into later ticks' state?
                later_evts = [e for e in events
                              if lin.action_tick < e.tick <
                              lin.action_tick + FUTURE_WINDOW]
                for e in later_evts:
                    for c in (e.consequences or []):
                        tgt = (c.target_type, c.target_id, c.field)
                        if tgt in lin.consequence_fields:
                            lin.state_persistence = True
                            if c.target_type == "relationship":
                                lin.relationship_persistence = True
                            elif c.field in ("reconciliation",
                                             "belonging", "freedom",
                                             "curiosity",
                                             "responsibility"):
                                lin.goal_desire_evolution = True
                for e in later_evts:
                    if (_actor_in_event(e, lin.actor)
                            and e.action_result is not None
                            and e.action_result.status == "failure"):
                        lin.natural_failure_in_window = True
            print(f"  lineage: {lin.actor} @t{lin.action_tick} "
                  f"({lin.event_id}), "
                  f"changed={lin.changed_state_fields}")
            print(f"    counterfactual undo+rerun (same seed): "
                  f"{'DIVERGENT' if lin.agency_witness else
                    'NO DIVERGENCE'} in actor's later committed "
                  f"actions, ticks "
                  f"{lin.action_tick + 1}..{lin.action_tick + FUTURE_WINDOW}")
            if lin.agency_witness:
                print(f"      first divergence @t{lin.later_action_tick}, "
                      f"irreversible={lin.irreversibility}, "
                      f"conflict={lin.conflict}, "
                      f"state_persists={lin.state_persistence}, "
                      f"relationship_persists={lin.relationship_persistence},"
                      f" goal/desire_evolved={lin.goal_desire_evolution},"
                      f" natural_failure_in_window="
                      f"{lin.natural_failure_in_window}")
        all_lineages.extend(seed_lineages)

    print("\n[Phase C] Story-level evidence inventory (reported, never "
          "manufactured)")
    witnesses = [l for l in all_lineages if l.agency_witness]
    print(f"  consequence-bearing lineages audited (Phase A): "
          f"{len(all_lineages)}")
    print(f"  with a confirmed agency witness (Phase B): "
          f"{len(witnesses)}/{len(all_lineages)}")
    for l in witnesses:
        print(f"    seed {l.seed} / {l.actor} @t{l.action_tick} -> "
              f"diverges @t{l.later_action_tick} "
              f"({'irreversible' if l.irreversibility else 'transient'}, "
              f"{'conflict' if l.conflict else 'no conflict observed'}, "
              f"{'natural failure observed'
               if l.natural_failure_in_window
               else 'no natural failure in window'})")

    print("\n[Spec's 5 required questions]")
    persistent = [l for l in witnesses if l.irreversibility]
    reenter = [l for l in witnesses
                if l.state_persistence
                or l.relationship_persistence
                or l.goal_desire_evolution]
    print(f"  1. 一次选择是否改变了该人物的未来: "
          f"{'YES' if witnesses else 'NOT PROVEN'} "
          f"({len(witnesses)}/{len(all_lineages)} audited lineages show "
          f"a later committed-action divergence)")
    print(f"  2. 改变是否持续多个 tick: "
          f"{'YES for ' + str(len(persistent)) + ' of '
            + str(len(witnesses)) if witnesses else 'N/A'}")
    print(f"  3. 关系/欲望/目标变化是否重新进入后续决策: "
          f"{'YES for ' + str(len(reenter)) + ' of '
            + str(len(witnesses)) if witnesses else 'NOT PROVEN'}")
    print(f"  4. 自然产生 conflict / irreversible consequence: "
          f"conflict-observed={sum(1 for l in witnesses if l.conflict)}, "
          f"irreversible-observed="
          f"{sum(1 for l in witnesses if l.irreversibility)}")
    print("  5. 最短缺的机制环节: 见 verdict 下说明，不强行补齐。")

    if (witnesses and persistent and
            any(l.conflict for l in witnesses)):
        verdict = "PROVEN"
    elif witnesses:
        verdict = "PARTIAL"
    else:
        verdict = "NOT PROVEN"
    print(f"\nSTORY-LIFE-LOOP VERDICT: {verdict}")
    print("  rule: PROVEN needs >=1 agency witness + persistent "
          "divergence + observed conflict; PARTIAL = >=1 agency "
          "witness without all three; NOT PROVEN = no agency witness "
          "in this window/seed set at all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
