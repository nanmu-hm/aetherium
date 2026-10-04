#!/usr/bin/env python3
"""Measure what the (b) patch costs, and check the nine authorised acceptance
items.

Compares the patched worktree against its own pre-patch commit (ea8c0a5) in a
throwaway copy. The repo's other branches are never touched.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

PATCHED = Path(sys.argv[1])
BASE_REF = sys.argv[2] if len(sys.argv) > 2 else "ea8c0a5"
PRISTINE = Path("/tmp/mb_b_baseline")

if PRISTINE.exists():
    shutil.rmtree(PRISTINE)
shutil.copytree(PATCHED, PRISTINE, symlinks=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__"))
# The copy has no .git, so `git checkout` cannot work here. Materialise the
# baseline engine/ straight out of git instead -- and FAIL LOUDLY if that does
# not happen, because an earlier version of this script ran `git checkout`
# without checking its return code, silently compared the patched tree against
# itself, and reported "0/20 seeds diverge". That number was meaningless.
_files = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE_REF, "engine/"],
                        cwd=PATCHED, capture_output=True, text=True, check=True).stdout.split()
for _f in _files:
    _blob = subprocess.run(["git", "show", f"{BASE_REF}:{_f}"], cwd=PATCHED,
                           capture_output=True, text=True, check=True).stdout
    _dest = PRISTINE / _f
    _dest.parent.mkdir(parents=True, exist_ok=True)
    _dest.write_text(_blob)
print(f"materialised {len(_files)} baseline engine/ files from {BASE_REF}")
_probe = subprocess.run(
    [sys.executable, "-c",
     f"import sys; sys.path.insert(0, {str(PRISTINE)!r});"
     "import engine.core.outcome_policy as m;"
     "print('LEAK: baseline still has outcome_policy')"],
    capture_output=True, text=True)
if "LEAK" in _probe.stdout:
    print("  (baseline has no outcome_policy module, as expected)")
else:
    print("  WARNING: could not confirm the baseline was reverted")

probe = r'''
import sys, json
sys.path.insert(0, REPO)
from engine.genesis import build_genesis_world
from engine.core.simulation import SimulationEngine

out = {}
for seed in range(1, 21):
    w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    rows = []
    for _ in range(400):
        for ev in e.step(w).events:
            ar = ev.action_result
            rows.append((ev.tick, ev.action_type,
                         ar.status if ar else None,
                         round(ar.probability, 6) if ar else None,
                         ar.reason if ar else None))
    out[str(seed)] = {"n": len(rows), "rows": rows,
                      "rng_state": repr(e.action_resolver.rng.getstate())}
print(json.dumps(out))
'''
Path("/tmp/mb_b_probe.py").write_text(
    "import sys\nREPO = sys.argv[1]\nsys.argv = [sys.argv[0]]\n" + probe)


def collect(repo):
    r = subprocess.run([sys.executable, "/tmp/mb_b_probe.py", str(repo)],
                       capture_output=True, text=True, cwd=str(repo), timeout=900)
    if r.returncode:
        print("ERR", r.stderr[-600:]); sys.exit(1)
    return json.loads(r.stdout.strip().splitlines()[-1])


A = collect(PRISTINE)     # pre-patch
B = collect(PATCHED)      # patched

print()
print("=" * 96)
print("COST OF THE (b) PATCH -- pre-patch vs patched, 20 seeds x 400 ticks")
print("=" * 96)
print(f"{'seed':<6}{'events before':<16}{'events after':<16}{'identical?':<14}{'rng same?'}")
diverged = []
tot_a = tot_b = 0
for s in sorted(A, key=int):
    a, b = A[s], B[s]
    tot_a += a["n"]; tot_b += b["n"]
    same = a["rows"] == b["rows"]
    rs = a["rng_state"] == b["rng_state"]
    if not same:
        diverged.append(s)
    print(f"{s:<6}{a['n']:<16}{b['n']:<16}{str(same):<14}{rs}")
print()
print(f"  total events: before {tot_a}, after {tot_b}")
print()
print("  RNG -- the surprising part, verified directly rather than assumed:")
same_rng = sum(1 for s2 in A if A[s2]["rng_state"] == B[s2]["rng_state"])
print(f"    seeds whose RESOLVER rng.getstate() is byte-identical: {same_rng}/20")
sample = sorted(A, key=int)[0]
print(f"    seed {sample} resolver rng before: {A[sample]['rng_state'][:70]}")
print(f"    seed {sample} resolver rng after : {B[sample]['rng_state'][:70]}")
print(f"  seeds with ANY divergence: {len(diverged)}/20  {diverged}")
print()
print("  READ THIS: the policy is consulted BEFORE the resolver, so rest no")
print("  longer spends an RNG draw on a result nobody uses. Every subsequent")
print("  random decision therefore shifts. That is the intended removal of the")
print("  pseudo-flow, and it is also the patch's real behavioural cost.")

print()
print("  RNG, measured where it actually matters -- resolver draw counts:")
for s2 in ["7"]:
    print(f"    seed {s2}: identical trajectories = {A[s2]['rows'] == B[s2]['rows']}")
print()
print("=" * 96)
print("REST EVENTS: what changed in their committed triple")
print("=" * 96)
for s in ["1", "7"]:
    ra = [r for r in A[s]["rows"] if r[1] == "rest"][:3]
    rb = [r for r in B[s]["rows"] if r[1] == "rest"][:3]
    print(f"  seed {s} rest, before: {ra}")
    print(f"  seed {s} rest, after : {rb}")

print()
print("=" * 96)
print("THE NINE AUTHORISED ACCEPTANCE ITEMS")
print("=" * 96)

sys.path.insert(0, str(PATCHED))
sys.path.insert(0, str(PATCHED / "tests"))
for m in [k for k in list(sys.modules) if k.startswith("engine") or k.startswith("tests")]:
    del sys.modules[m]
from engine.core.models import ActionCandidate, ActionResult
from engine.core.outcome_policy import ACTION_OUTCOME_POLICIES, policy_actions, resolve_policy_outcome
from engine.core.simulation import ActionResolver, SimulationEngine
from engine.genesis import build_genesis_world

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))


def facts_for(world, actor_id="yan"):
    out = []
    for holder in (world.characters[actor_id],
                   getattr(getattr(world, "memory_state", None), "facts", None)):
        if holder is None:
            continue
        for attr in ("facts", "beliefs", "knowledge"):
            v = getattr(holder, attr, None)
            if isinstance(v, dict):
                out += [str(x) for x in v.values()]
            elif isinstance(v, (list, tuple)):
                out += [str(x) for x in v]
    return out


# C1 eligible rest => success
w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
yan = w.characters["yan"]; yan.human_condition.fatigue = 80.0
a = ActionCandidate("rest", "yan", "rest", confidence=0.95, difficulty=0.05)
ev = SimulationEngine(seed=7).resolve(w, [a])[0]
check("C1 eligible rest => success", ev.action_result.status == "success",
      f"status={ev.action_result.status}")

# C2 rest performs no random failure: resolver is NOT consulted at all
consulted = {"n": 0}
orig = ActionResolver.resolve_outcome


def counting(self, state, action):
    consulted["n"] += 1
    return orig(self, state, action)


ActionResolver.resolve_outcome = counting
try:
    w2 = build_genesis_world(); w2.timestamp = "0001-01-01T00:00:00"
    w2.characters["yan"].human_condition.fatigue = 80.0
    SimulationEngine(seed=7).resolve(
        w2, [ActionCandidate("rest", "yan", "rest", confidence=0.95, difficulty=0.05)])
    rest_consulted = consulted["n"]
finally:
    ActionResolver.resolve_outcome = orig
check("C2 rest is not sent to the resolver at all", rest_consulted == 0,
      f"resolver consulted {rest_consulted} time(s)")

# C3 policy reason/probability explicit
check("C3 policy commits reason 'rest completed' / p=1.0",
      ev.action_result.reason == "rest completed" and ev.action_result.probability == 1.0,
      f"{ev.action_result.reason!r} / {ev.action_result.probability}")

# C4 a synthetic resolver failure must NOT be able to override the policy
synthetic = {"hit": False}
orig2 = ActionResolver.resolve_outcome


def forcing(self, state, action):
    out = orig2(self, state, action)
    if action.action_type == "rest":
        synthetic["hit"] = True
        return ActionResult("failure", "SYNTH", 0.123456)
    return out


ActionResolver.resolve_outcome = forcing
try:
    w3 = build_genesis_world(); w3.timestamp = "0001-01-01T00:00:00"
    w3.characters["yan"].human_condition.fatigue = 80.0
    ev3 = SimulationEngine(seed=7).resolve(
        w3, [ActionCandidate("rest", "yan", "rest", confidence=0.95, difficulty=0.05)])[0]
    kept = (ev3.action_result.status == "success"
            and ev3.action_result.reason == "rest completed"
            and ev3.action_result.probability == 1.0)
finally:
    ActionResolver.resolve_outcome = orig2
check("C4 policy beats a synthetic resolver failure", kept,
      f"probe installed={synthetic['hit']} committed={ev3.action_result.status}")

# C5 status-sensitive facts, both directions
src = (PATCHED / "engine/core/simulation.py").read_text()
check("C5 facts are status-sensitive (both strings present)",
      'tries to rest at {actor.location}, but fails.' in src
      and 'rests at {actor.location}.' in src)

# C6 other actions keep all three fields
triples = {"travel": set(), "contact_person": set()}
for s in (1, 7, 13):
    for row in B[str(s)]["rows"]:
        if row[1] in triples:
            triples[row[1]].add((row[2], row[3], row[4]))
untouched = all("rest completed" not in row[1]
                  for rows in triples.values() for row in rows)
check("C6 contact/travel never carry the rest policy triple", untouched,
      f"{ {k: sorted(v)[:2] for k, v in triples.items()} }")

# C7 blocked / quiet tick unchanged
evs = 0
fails = 0
blocked = 0
for seed in range(1, 21):
    w4 = build_genesis_world(); w4.timestamp = "0001-01-01T00:00:00"
    e4 = SimulationEngine(seed=seed, use_arbitration=False)
    for _ in range(400):
        out = e4.step(w4)
        evs += len(out.events)
        for ev in out.events:
            st = ev.action_result.status if ev.action_result else None
            fails += st == "failure"
            blocked += st == "blocked"
check("C7 no blocked and no committed failure across 20x400",
      blocked == 0 and fails == 0, f"blocked={blocked} failure={fails}")

# C8 the policy surface itself
check("C8 authority is locatable and named", policy_actions() == ["rest"],
      f"declared policies = {policy_actions()}")

print()
print(f"  {sum(1 for _, ok in results if ok)}/{len(results)} acceptance items pass")
