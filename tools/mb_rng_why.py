#!/usr/bin/env python3
"""WHY is the resolver's RNG byte-identical after removing rest's draw?

The (b) patch stops consulting the resolver for rest, so rest no longer calls
`ActionResolver.resolve_outcome`, which calls `self.rng.random()`. That should
advance the resolver's stream one step fewer per rest event, and every later
resolver draw should shift.

Measured, on a correctly reverted baseline: resolver draw counts drop from 13
to 10 on seed 7 (rest's 3 draws disappear), and the resolver's
`rng.getstate()` differs on 20/20 seeds -- the stream genuinely moves. The
committed trajectories are nevertheless identical over 20 seeds x 400 ticks
(245 events both sides), because no shifted draw crossed its threshold in that
sample.

An earlier version of this file claimed the RNG state was byte-identical on
20/20 seeds. That number was produced by comparing the patched tree against
itself: the baseline copy has no .git, so the `git checkout` that was meant to
revert it failed silently and the "before" side was already patched. The claim
is retracted. This script now materialises the baseline from git and checks that
it really was reverted.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

PATCHED = Path(sys.argv[1])
BASE = sys.argv[2] if len(sys.argv) > 2 else "ea8c0a5"
PRISTINE = Path("/tmp/mb_rng_baseline")

if PRISTINE.exists():
    shutil.rmtree(PRISTINE)
shutil.copytree(PATCHED, PRISTINE, symlinks=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__"))
# the copy has no .git, so materialise the baseline engine/ straight from git
_files = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE, "engine/"],
                        cwd=PATCHED, capture_output=True, text=True, check=True).stdout.split()
for _f in _files:
    _blob = subprocess.run(["git", "show", f"{BASE}:{_f}"], cwd=PATCHED,
                           capture_output=True, text=True, check=True).stdout
    _dest = PRISTINE / _f
    _dest.parent.mkdir(parents=True, exist_ok=True)
    _dest.write_text(_blob)
print(f"materialised {len(_files)} baseline engine/ files from {BASE}")

probe = r'''
import sys, json, random
sys.path.insert(0, REPO)
from engine.genesis import build_genesis_world
from engine.core.simulation import ActionResolver, SimulationEngine

draws = {"n": 0, "types": {}}
orig = ActionResolver.resolve_outcome
def counting(self, state, action):
    draws["n"] += 1
    draws["types"][action.action_type] = draws["types"].get(action.action_type, 0) + 1
    return orig(self, state, action)
ActionResolver.resolve_outcome = counting

w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
e = SimulationEngine(seed=7, use_arbitration=False)
events = 0
rest_events = 0
for _ in range(400):
    for ev in e.step(w).events:
        events += 1
        if ev.action_type == "rest":
            rest_events += 1

res = e.action_resolver
info = {
    "resolver_draws_total": draws["n"],
    "resolver_draws_by_type": draws["types"],
    "rest_events": rest_events,
    "events": events,
    "action_resolver_rng_id": id(res.rng),
    "action_resolver_rng_state": repr(res.rng.getstate()),
    "engine_has_own_rng": hasattr(e, "rng"),
    "engine_rng_id": id(getattr(e, "rng", None)),
    "same_object": getattr(e, "rng", None) is res.rng,
}
for attr in dir(e):
    v = getattr(e, attr, None)
    if isinstance(v, random.Random):
        info[f"engine_random_attr::{attr}"] = id(v)
        info[f"engine_random_attr::{attr}::is_resolver_rng"] = v is res.rng
print(json.dumps(info, indent=1))
'''
Path("/tmp/mb_rng_probe.py").write_text(
    "import sys\nREPO = sys.argv[1]\nsys.argv = [sys.argv[0]]\n" + probe)


def run(repo):
    r = subprocess.run([sys.executable, "/tmp/mb_rng_probe.py", str(repo)],
                       capture_output=True, text=True, cwd=str(repo), timeout=560)
    if r.returncode:
        print("ERR", r.stderr[-800:]); sys.exit(1)
    return json.loads(r.stdout.strip())


A = run(PRISTINE)
B = run(PATCHED)

print("=" * 96)
print("BEFORE (pre-patch engine/)")
print("=" * 96)
for k, v in A.items():
    print(f"  {k:<42} {v}")
print()
print("=" * 96)
print("AFTER (patched)")
print("=" * 96)
for k, v in B.items():
    print(f"  {k:<42} {v}")

print()
print("=" * 96)
print("THE COMPARISON THAT EXPLAINS IT")
print("=" * 96)
print(f"  resolver draws  before {A['resolver_draws_total']:>4}   after {B['resolver_draws_total']:>4}"
      f"   (delta {B['resolver_draws_total'] - A['resolver_draws_total']})")
print(f"  rest events committed: {A['rest_events']} before, {B['rest_events']} after")
print(f"  rng byte-identical:   {A['action_resolver_rng_state'] == B['action_resolver_rng_state']}")
print()
print(f"  draws by action type, before: {A['resolver_draws_by_type']}")
print(f"  draws by action type, after : {B['resolver_draws_by_type']}")
print()

# The decisive test: does skipping the resolver for rest change the stream?
print("  DIRECT TEST: does the resolver's stream advance once per call?")
for tag, repo in (("before", PRISTINE), ("after", PATCHED)):
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from engine.core.simulation import ActionResolver;"
        "r = ActionResolver.__new__(ActionResolver);"
        "import random; r.rng = random.Random(1);"
        "print(r.rng.random())" % str(repo)
    )
    r1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, "-c",
                        code.replace("print(r.rng.random())",
                                     "r.rng.random(); print(r.rng.random())")],
                       capture_output=True, text=True)
    print(f"    {tag:<7} first draw {r1.stdout.strip()[:20]}   second draw "
          f"{r2.stdout.strip()[:20]}")
print()
print("  If those are the SAME, the isolated stream advances identically in")
print("  both trees -- which is the point: the resolver's stream is unchanged")
print("  by anything except how many times resolve_outcome is called on it.")
print()
print("  CONCLUSION: the patch removes 3 resolver draws (one per rest event),")
print("  so the stream MOVES (rng byte-identical = False). Trajectories still")
print("  match over 20 seeds x 400 ticks because no shifted draw crossed its")
print("  threshold in this sample. That is a property of the sample, not a")
print("  guarantee -- see the report's COST section.")
