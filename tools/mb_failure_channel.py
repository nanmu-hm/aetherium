"""Q1: is there ANY formal failure / obstruction / rejection channel?

ChatGPT 5976864889, read-only, no production edits, no fix pre-registration.

Q1 asks for a full trace of
    candidate generation -> validation / hard gate -> rejection / failure
    -> consequence -> psychology delta -> distress
and specifically NOT just the sorrow/fear write sites: it asks why the
currently reachable actions almost never produce a failure consequence that
could form distress.

Everything below is a census of the existing code, not a proposal.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def grep(pattern, path="engine", extra=()):
    out = subprocess.run(
        ["grep", "-rn", pattern, "--include=*.py", *extra, path],
        capture_output=True, text=True).stdout
    return [l.split("/engine/")[-1] for l in out.splitlines()]


print("=" * 96)
print("Q1a. EVERY 'failure' concept in the codebase")
print("=" * 96)
for pat in ("failure", "failed", "rejected", "refus", "blocked", "obstruct",
            "unmet", "missed", "prevented", "denied", "impossible", "cannot"):
    hits = grep(pat)
    print()
    print(f"--- {pat!r}: {len(hits)} hits ---")
    for h in hits[:14]:
        print("   ", h)
    if len(hits) > 14:
        print(f"    ... {len(hits) - 14} more")

print()
print("=" * 96)
print("Q1b. the ActionResult / outcome type -- what statuses exist?")
print("=" * 96)
out = subprocess.run(
    ["grep", "-n", "-A", "25", "class ActionResult", "engine/core/models.py"],
    capture_output=True, text=True).stdout
print(out)
print("--- every status literal assigned anywhere ---")
for h in grep(r'status\s*=\s*"'):
    print("   ", h)

print()
print("=" * 96)
print("Q1c. the FAILED branch of event outcome -- does it exist?")
print("=" * 96)
out2 = subprocess.run(
    ["sed", "-n", "230,270p", "engine/core/simulation.py"],
    capture_output=True, text=True).stdout
print(out2)

print()
print("=" * 96)
print("Q1d. which action outcomes actually occur in the 5-seed baseline?")
print("=" * 96)
from engine.core.simulation import SimulationEngine
from engine.genesis import build_genesis_world
from collections import Counter

for seed in (1, 2, 3, 7, 42):
    w = build_genesis_world()
    w.timestamp = "0001-01-01T00:00:00"
    e = SimulationEngine(seed=seed, use_arbitration=False)
    statuses = Counter()
    results = []
    for _ in range(200):
        r = e.step(w)
        for ev in r.events:
            st = ev.action_result.status if ev.action_result else "no-result"
            statuses[(ev.action_type, st)] += 1
            results.append((ev.tick, ev.action_type, st))
    failures = [(t, a, s) for (a, s), n in statuses.items() if s != "success" for t in [0]]
    total = sum(statuses.values())
    non_success = sum(n for (a, s), n in statuses.items() if s != "success")
    print()
    print(f"   seed {seed}: {total} events, non-success outcomes = {non_success}")
    for (a, s), n in sorted(statuses.items()):
        print(f"      {a:<16} {s:<10} {n}")
    if non_success == 0:
        print("      => NO failure outcome ever occurs in this baseline")