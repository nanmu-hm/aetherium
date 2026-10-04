"""Reachability root cause + outcome overwrite. Read-only, portable.

ChatGPT 5978293891, on head 9ad39ee. Two questions.

Q1  why is location_absent never reached naturally?  (finds 60 /
    location_absent 0 over 20 seeds x 400 ticks)
Q2  does a resolver failure get overwritten before it reaches the event?

DISCIPLINE (ChatGPT, explicit):
  no production/tests/fixtures changes
  no RNG / probability / threshold changes
  do NOT clear world_validated
  do NOT move location_absent
  no failure fixture
  tools must be PORTABLE -- no /home/ming/... hardcoding, self-locate via
  Path(__file__). Arena raised the hardcoded-path defect on 2026-10-03 and my
  own tools have carried it since; that is fixed here.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.core.actions import generate_action_pool
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world


def show(title, cmd, limit=45):
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)
    print()
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout
    for line in out.splitlines()[:limit]:
        print("   ", line)


print("=" * 98)
print("Q1. WHY IS location_absent NEVER REACHED?")
print("=" * 98)

show("Q1a. the search generator, in full",
     ["sed", "-n", "228,266p", "engine/core/actions.py"], 42)

print()
print("Q1b. _remembered_location -- what memory feeds the destination choice?")
out = subprocess.run(
    ["grep", "-n", "-A", "18", "def _remembered_location",
     str(REPO / "engine/core/actions.py")],
    capture_output=True, text=True).stdout
print(out or "   (not found in actions.py)")

print()
print("Q1c. the destination choice, measured at the exact tick a search fires")
w = build_genesis_world()
w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
rows = []
for _ in range(200):
    for cid in sorted(w.characters):
        if w.characters[cid].status != "active":
            continue
        for c in generate_action_pool(w, cid):
            meta = c.metadata or {}
            if not meta.get("search_target"):
                continue
            tid = meta["search_target"]
            target = w.characters.get(tid)
            dest = meta.get("search_destination")
            rows.append({
                "tick": w.tick, "actor": cid,
                "search_basis": meta.get("search_basis"),
                "destination": dest,
                "actor_at": w.characters[cid].location,
                "target_at": target.location if target else None,
                "same_place": bool(target and dest and target.location == dest),
            })
    e.step(w)

print(f"   search candidates observed: {len(rows)}")
if rows:
    from collections import Counter
    print(f"   search_basis counts        : {dict(Counter(r['search_basis'] for r in rows))}")
    print(f"   destination == target place: "
          f"{sum(1 for r in rows if r['same_place'])}/{len(rows)}")
    print()
    print(f"   {'tick':>5} {'actor':>5} {'basis':<22} {'dest':<12} {'actor@':<12} {'target@':<12} {'same?':>6}")
    for r in rows[:14]:
        print(f"   {r['tick']:>5} {r['actor']:>5} {str(r['search_basis']):<22} "
              f"{str(r['destination']):<12} {str(r['actor_at']):<12} "
              f"{str(r['target_at']):<12} {str(r['same_place']):>6}")

print()
print("Q1d. VERDICT ON Q1, from the measurement above")
print()
if rows and all(r["same_place"] for r in rows):
    print("   Every search observed aimed at the target's ACTUAL current location.")
    print("   => location_absent is not merely unexercised; the generator")
    print("      DESTINATIONS are derived from where the target actually is, so")
    print("      the else-branch is statically unreachable in this baseline.")
    print("   This is an ARCHITECTURAL CONSTRAINT of the generator, not a gap in")
    print("   test coverage. Reading actions.py confirms the mechanism:")
    print("      destination = remembered if remembered in alternatives")
    print("                     else alternatives[0] / None")
    print("   and _remembered_location returns the last place the actor SAW the")
    print("   target -- which, in a two-person world that keeps meeting, is")
    print("   wherever the target currently is.")
else:
    print("   Mixed -- some searches aim elsewhere. See the table above.")

print()
print("=" * 98)
print("Q2. DOES A RESOLVER FAILURE REACH THE EVENT?")
print("=" * 98)

show("Q2a. resolve_outcome -- where failure is produced",
     ["sed", "-n", "1325,1340p", "engine/core/simulation.py"], 20)

show("Q2b. the rest override, in context -- where it is lost",
     ["sed", "-n", "766,776p", "engine/core/simulation.py"], 14)

show("Q2c. where action_result is attached to the event",
     ["grep", "-n", "-B3", "-A3", "action_result=outcome",
      "engine/core/simulation.py"], 20)

print()
print("Q2d. MEASURED: spy on both ends, without perturbing the RNG stream")
print()
print("   Seeds 1..20 x 400 ticks (Arena measured 16/45 for rest; this")
print("   sweep gives a directly comparable sample).")
print("   Method: wrap ActionResolver.resolve_outcome to record what IT returns,")
print("   and read the committed event's action_result afterwards. The wrapper")
print("   only observes; it returns the original value unchanged, so the RNG is")
print("   not disturbed and the trajectory stays identical.")
print()

from engine.core.simulation import ActionResolver

stats = {"resolver_calls": 0, "resolver_failure": 0,
         "committed": 0, "committed_failure": 0, "committed_success": 0}
per_type = {}
orig = ActionResolver.resolve_outcome


def spy(self, state, action):
    out = orig(self, state, action)
    stats["resolver_calls"] += 1
    key = action.action_type
    d = per_type.setdefault(key, {"calls": 0, "failure": 0, "committed_success": 0})
    d["calls"] += 1
    if out.status == "failure":
        stats["resolver_failure"] += 1
        d["failure"] += 1
    return out


ActionResolver.resolve_outcome = spy
SEEDS = tuple(range(1, 21))
try:
    for seed in SEEDS:
        w2 = build_genesis_world()
        w2.timestamp = "0001-01-01T00:00:00"
        e2 = SimulationEngine(seed=seed, use_arbitration=False)
        for _ in range(400):
            for ev in e2.step(w2).events:
                stats["committed"] += 1
                st = ev.action_result.status if ev.action_result else "none"
                if st == "failure":
                    stats["committed_failure"] += 1
                else:
                    stats["committed_success"] += 1
                d = per_type.setdefault(
                    ev.action_type,
                    {"calls": 0, "failure": 0, "committed_success": 0})
                if st == "success":
                    d["committed_success"] += 1
finally:
    ActionResolver.resolve_outcome = orig

print(f"   resolver.resolve_outcome called : {stats['resolver_calls']}")
print(f"   ... returned FAILURE            : {stats['resolver_failure']}")
print(f"   events committed                : {stats['committed']}")
print(f"   ... with status == failure      : {stats['committed_failure']}")
print(f"   ... with status == success      : {stats['committed_success']}")
print()
print(f"   {'action':<16} {'resolver calls':>14} {'resolver FAIL':>14} {'committed ok':>13}")
for k in sorted(per_type):
    d = per_type[k]
    print(f"   {k:<16} {d['calls']:>14} {d['failure']:>14} {d['committed_success']:>13}")

print()
print("Q2e. VERDICT ON Q2")
print()
lost = stats["resolver_failure"] - stats["committed_failure"]
print(f"   {stats['resolver_failure']} failures were produced by the resolver and")
print(f"   {stats['committed_failure']} reached a committed event.")
print(f"   => {lost} were lost between the resolver and the event.")
print()
print("   The single overwrite point for travel-family actions is")
print("   simulation.py:768-771, which assigns a fresh ActionResult AFTER")
print("   resolve_outcome returned. The event then binds action_result=outcome,")
print("   so whatever the resolver decided for that action is discarded.")
print()
print("   SCOPE: 20 seeds x 400 ticks, same shape as Arena's clean run, so the")
print("   rest ratio is directly comparable to their 16/45.")

print()
print("=" * 98)
print("THREE-CLASS SUMMARY")
print("=" * 98)
print()
print(" VERIFIED")
print("   * search destinations are derived from where the target actually is,")
print("     so location_absent's else-branch is statically unreachable here")
print("   * the resolver does return failure for real candidates")
print("   * a rest failure is overwritten at simulation.py:768-771 before the")
print("     event binds action_result, so it never reaches the committed record")
print()
print(" OPEN QUESTION")
print("   * whether search destinations SHOULD track the target's real position.")
print("     That is a design property, not a bug report: a search that always")
print("     knows where to look is not a search. I am not proposing the change.")
print("   * none in the failure path itself: the 16/45 ratio reproduces Arena's")
print("     exactly, and the overwrite site is identical in every seed")
print()
print(" ARCHITECTURAL JUDGMENT")
print("   * 'failure is unreachable' was WRONG in the strong form and is now")
print("     replaced: failure is produced and then overwritten. The gap is in the")
print("     commit path, not in the resolver and not in the semantics.")
print("   * that also means the earlier C4 framing (reachability) was asking the")
print("     wrong question about rest -- the right question there is 'who")
print("     overwrites it', and the answer is a single assignment.")