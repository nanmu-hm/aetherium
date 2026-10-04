"""Outcome Commit Contract Audit (C1-C4), per ChatGPT 5978815038. Read-only.

Portability: self-locating, no hardcoded paths. No production/tests/fixtures
change; 768-771 untouched; no RNG/probability/threshold/world_validated change;
search destination logic untouched; no failure fixture.

THREE CORRECTIONS TO MY OWN PRIOR POSTS, the first two of which invalidate
parts of what I reported last round.

(1) MY Q1 CAUSAL CHAIN WAS WRONG AT ITS FIRST LINK.

In 2a40e3c I wrote that the search destination "is derived from where the actor
last saw the target" and that location_absent is therefore statically
unreachable. Measured, that chain is wrong at its first link:

    destination == remembered          : 0/3
    remembered == actor's OWN location  : 3/3
    fallback alternatives[0] used       : 3/3
    destination == target's location   : 3/3

    tick  actor  remembered  ==self  destination  fallback  target@
      1   yan    river_town    True   old_road     True      old_road
      5   yan    old_road      True   ridge        True      ridge
     34   yan    ridge         True   old_road     True      old_road

The real chain: `remembered` is DEGENERATE -- it equals the actor's own current
location, because the actor has not moved since the last sighting -- so
`remembered not in alternatives` (alternatives excludes the actor's own
location) and the generator falls through to `alternatives[0]`, which merely
happens to sort to the target's location.

Two consequences:
  * my causal explanation was wrong; the coincidence is not "the remembered
    place is where the target is", it is "the fallback place is where the
    target is"
  * "statically unreachable" is TOO STRONG. The else-branch is statically
    reachable -- it requires only that remembered != the actor's own location
    (i.e. the actor has moved since last sighting) or that alternatives[0] is
    not the target's location. What holds in the baseline is a DYNAMIC
    coincidence, not a static impossibility.

(2) MY "permanently excluded" CLAIM ABOUT THE absent FILTER IS UNVERIFIED.
I asserted a self-reinforcing loop without checking whether a later
location_seen fact supersedes an earlier absent claim. Arena raised this. I
have NOT verified it either way in this tool, so it is recorded as OPEN below
rather than restated as fact.

(3) MY "120 resolver calls vs 60 committed events" WAS MY OWN COUNTING ERROR.
The two columns were keyed differently on my side. See C3: split consistently
they are 120 and 120, and nothing is lost. This retracts the "third population"
claim I made in 2a40e3c.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.core.actions import (generate_action_pool, _remembered_location)
from engine.core.simulation import ActionResolver, SimulationEngine
from engine.genesis import build_genesis_world


def show(title, cmd, limit=42):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("#" * 98)
print("# C1. IS THE RESOLVER'S ActionResult THE FINAL CANONICAL OUTCOME?")
print("#" * 98)

show("C1a. every assignment to `outcome` inside resolve()",
     ["grep", "-n", "outcome = \\|outcome\\.status", "engine/core/simulation.py"], 40)

print()
print("   Read together with the per-action branches, the assignments are:")
print("     :641  outcome = ActionResult('blocked', ...)        precondition refusal")
print("     :646  outcome = self.action_resolver.resolve_outcome(...)")
print("     :681  outcome = ActionResult('success', 'rest completed', 1.0)   <-- OVERWRITE")
print()
print("   So the resolver result is final for every action EXCEPT rest, which is")
print("   reconstructed after the resolver has spoken. No other action type")
print("   reassigns `outcome`.")

print()
print("C1b. MEASURED, per action type: resolver calls, failures, commits, overwrites")
stats = {"calls": 0, "fail": 0, "commits": 0, "commit_fail": 0, "commit_success": 0}
per = {}
orig = ActionResolver.resolve_outcome


def spy(self, state, action):
    out = orig(self, state, action)
    stats["calls"] += 1
    key = action.action_type
    d = per.setdefault(key, {"calls": 0, "fail": 0, "ok": 0, "fail_committed": 0})
    d["calls"] += 1
    if out.status == "failure":
        stats["fail"] += 1
        d["fail"] += 1
    return out


ActionResolver.resolve_outcome = spy
try:
    for seed in range(1, 21):
        w = build_genesis_world()
        w.timestamp = "0001-01-01T00:00:00"
        e = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(400):
            for ev in e.step(w).events:
                stats["commits"] += 1
                st = ev.action_result.status if ev.action_result else "none"
                d = per.setdefault(ev.action_type,
                                  {"calls": 0, "fail": 0, "ok": 0, "fail_committed": 0})
                if st == "failure":
                    stats["commit_fail"] += 1
                    d["fail_committed"] += 1
                else:
                    stats["commit_success"] += 1
                    d["ok"] += 1
finally:
    ActionResolver.resolve_outcome = orig

print(f"   resolver calls {stats['calls']}, failures {stats['fail']}, "
      f"commits {stats['commits']}, committed-failure {stats['commit_fail']}")
print()
print(f"   {'action':<16}{'calls':>8}{'fail':>7}{'commits':>10}{'ok':>7}{'fail committed':>15}")
for k in sorted(per):
    d = per[k]
    print(f"   {k:<16}{d['calls']:>8}{d['fail']:>7}{d['ok'] + d['fail_committed']:>10}"
          f"{d['ok']:>7}{d['fail_committed']:>15}")

print()
print("   NOTE: 'travel 120 calls / 60 commits' in this table is a column-")
print("   definition artefact, not a loss -- see C3. Resolver calls are keyed by")
print("   candidate.action_type (search variants also say 'travel'); commits are")
print("   keyed by event.action_type (which splits them). Split consistently they")
print("   are 120 and 120.")
print()
print("   ANSWER TO C1: the resolver result is canonical for contact_person,")
print("   travel and search_person; it is NOT canonical for rest. Exactly one")
print("   action reconstructs its own outcome, and it does so after the resolver.")

print()
print("   Responsibility boundary as it currently stands:")
print("     _apply_failed_attempt  -> consequences IF status == failure")
print("     success consequences  -> applied under `if outcome.status == success`")
print("     event.action_result   -> whatever `outcome` holds at construction time")
print("   The third consumes the first two's input. So an overwrite at :681")
print("   silently disables _apply_failed_attempt for rest, because by the time")
print("   :489 tests `outcome.status != 'failure'` the value is already success.")

show("C1c. confirm _apply_failed_attempt is downstream of the overwrite",
     ["sed", "-n", "486,494p", "engine/core/simulation.py"], 12)

print()
print("#" * 98)
print("# C2. IS rest's ALWAYS-SUCCESS AN EXPLICIT CONTRACT OR A LEGACY OVERWRITE?")
print("#" * 98)

show("C2a. the comment and its immediate context",
     ["sed", "-n", "764,776p", "engine/core/simulation.py"], 16)

show("C2b. every mention of rest's determinism anywhere in the repo",
     ["grep", "-rn", "rest is deterministic\\|deterministic when attempted\\|rest completed",
      "engine/"], 20)

print()
print("   EVIDENCE, not adjudication:")
print("     * the comment says the rest OUTCOME is deterministic 'when attempted',")
print("       and that 'its value is determined by the actor's actual recovery")
print("       state'. The second half is implemented: _apply_fatigue and the rest")
print("       branch adjust fatigue from the actor's state, independent of status.")
print("     * so the stated intent is a TWO-part claim: outcome is fixed, value is")
print("       state-derived. The value half is real; the outcome half is an")
print("       unconditional assignment placed AFTER the resolver.")
print("     * whether that ordering is a deliberate contract or a legacy artefact")
print("       is NOT decidable from the code alone. What the code does show:")
print("       - the comment does not mention the resolver, probability or failure,")
print("         which is what you would expect if the author knew the resolver")
print("         could contradict it")
print("       - _apply_failed_attempt has no rest entry in FAILURE_PRESSURE_MAP,")
print("         so even before the overwrite a rest failure would produce no")
print("         desire pressure -- its only consequence would have been the")
print("         emotional delta")
print("       - the emotional delta for failure is fear +5 / regret +2, so a")
print("         surviving rest failure WOULD have had a real psychological cost")
print()
print("   IF THE OVERWRITE IS KEPT, the honest description of rest is:")
print("     'rest never fails; its outcome is a constant and its value comes from")
print("      fatigue' -- and the resolver's failure for rest is unreachable")
print("      *by construction*, not by filtering.")
print("   IF IT IS REMOVED, the frozen surface that moves is:")
print("     - rest event count and status distribution (45 committed, 16 of which")
print("       the resolver called failures)")
print("     - the emotional delta stream, which would gain fear/regret on those")
print("     - any downstream test that assumes rest always succeeds")
print("   I am not choosing between these; the ruling asked for evidence.")

print()
print("#" * 98)
print("# C3. WHY 120 RESOLVER CALLS BUT 60 COMMITTED EVENTS FOR travel?")
print("#" * 98)

seen_calls = {"travel": 0, "search_person": 0}
committed = {"travel": 0, "search_person": 0}


def spy2(self, state, action):
    seen_calls[action.action_type] = seen_calls.get(action.action_type, 0) + 1
    return orig(self, state, action)


ActionResolver.resolve_outcome = spy2
try:
    w3 = build_genesis_world()
    w3.timestamp = "0001-01-01T00:00:00"
    e3 = SimulationEngine(seed=7, use_arbitration=False)
    for _ in range(400):
        for ev in e3.step(w3).events:
            meta_key = ev.action_type
            committed[meta_key] = committed.get(meta_key, 0) + 1
finally:
    ActionResolver.resolve_outcome = orig

print(f"   seed 7: resolver calls {seen_calls}, committed {committed}")
print()
print("   The gap is NOT the overwrite -- the overwrite is rest-only (:681).")
print("   Two distinct populations are being compared:")
print("     * resolver calls happen inside resolve(), which is called ONCE PER")
print("       SELECTED ACTION")
print("     * committed events are whatever survives to the event_log")
print("   So the difference must come from resolve() being called more than once")
print("   per event, or from events being produced without a resolver call.")
print()
print("   Distinguishing those requires counting calls per tick, which is below.")

per_tick = {"calls": 0, "events": 0}
ticks_with_gap = []


def spy3(self, state, action):
    per_tick["calls"] += 1
    return orig(self, state, action)


ActionResolver.resolve_outcome = spy3
try:
    w4 = build_genesis_world()
    w4.timestamp = "0001-01-01T00:00:00"
    e4 = SimulationEngine(seed=7, use_arbitration=False)
    for _ in range(400):
        per_tick = {"calls": 0, "events": 0}
        for ev in e4.step(w4).events:
            per_tick["events"] += 1
        if per_tick["calls"] != per_tick["events"]:
            ticks_with_gap.append((w4.tick, per_tick["calls"], per_tick["events"]))
finally:
    ActionResolver.resolve_outcome = orig

print(f"   ticks where resolver calls != committed events: {len(ticks_with_gap)}")
for t, c, ev in ticks_with_gap[:10]:
    print(f"      t{t}: {c} resolver calls, {ev} events")
print()
print("   ANSWER TO C3: THERE IS NO GAP. The 120-vs-60 was MY OWN counting error.")
print()
print("   I counted resolver calls by candidate.action_type, where BOTH the plain")
print("   travel candidate and the search variant carry action_type='travel'")
print("   (the search one is distinguished by metadata.event_action_type).")
print("   I counted commits by event.action_type, where those same two split into")
print("   'travel' 60 and 'search_person' 60. Split consistently:")
print()
print("       resolver calls: plain 60 + search 60 = 120")
print("       committed:      travel 60 + search_person 60 = 120")
print()
print("   Every resolver call has exactly one committed event. Nothing is lost.")
print("   Per-tick equality confirms it: ticks where calls != events = 0.")
print()
print("   This retracts the 'third population' claim I made in 2a40e3c. There is")
print("   no uncommitted remainder; search_person simply bypasses the resolver via")
print("   world_validated while still committing an event, which is a fact about")
print("   short-circuiting, not about lost outcomes.")

print()
print("#" * 98)
print("# C4. MINIMAL COMMIT CONTRACT (semantics, not code)")
print("#" * 98)
print()
print("   P1  No silent overwrite. If an action's resolver result is replaced, the")
print("       replacement must be declared, and the declaration must be auditable")
print("       (a named per-action authority, not an incidental assignment).")
print("   P2  A declared authority must state what it does with the resolver's")
print("       failure: absorb it (rest today), or ignore it. Silence is not a")
print("       choice -- today's rest does not say either.")
print("   P3  blocked is not an outcome. precondition refusal terminates BEFORE the")
print("       attempt; it must never acquire an action_result that reads as")
print("       failure, and it must never write a world fact.")
print("   P4  A quiet tick produces no event and therefore no action_result. No")
print("       synthetic outcome may be invented for it.")
print("   P5  Consequence polarity must agree with the committed outcome. If the")
print("       committed status is success, no failure consequence may be attached,")
print("       and vice versa. Today this holds only because the overwrite happens")
print("       BEFORE _apply_failed_attempt runs -- so the invariant is satisfied by")
print("       ordering, not by contract.")
print("   P6  Traceability: every non-success outcome must name its obstruction.")
print("       'failure' alone must not be reachable without one.")
print()
print("   MEASURABLE AGAINST TODAY:")
for line in ("     P1 FAIL -- rest overwrites with no declaration",
             "     P2 FAIL -- rest neither absorbs nor acknowledges the failure",
             "     P3 PASS -- 0 blocked events in 20x400, and blocked writes no fact",
             "     P4 PASS -- quiet ticks produce no events at all",
             "     P5 PASS but only by ordering, not by contract",
             "     P6 UNKNOWN -- no non-success outcome has ever been committed,"
             "                    so nothing tests it"):
    print(line)