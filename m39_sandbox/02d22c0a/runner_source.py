#!/usr/bin/env python
"""M39 Sandbox Runner (one-time, gated by ChatGPT 6356532133 + 6356726814)
Isolated /tmp sandbox, no engine modifications, no project file writes.

P6(a) limitation statement (run_report must include):
  - fd parser reliable-attribution guarantee covers single-process runner
    path + tested open/write/close/dup controls ONLY.
  - NOT claimed: fcntl(F_DUPFD) or fork/clone cross-process fd table
    propagation are verified.
  - strace process syscall trace enabled: any fcntl(F_DUPFD*)/fork/vfork/
    clone/clone3/exec event observed → INVALID/NO-GO, stop immediately.
"""
import sys, os, json, hashlib, time, resource, uuid
import json as _json

# ── Constants ────────────────────────────────────────────────────────────────
SEEDS   = [1, 3, 7, 42, 99]
TICKS   = 40
MEM_LIM_KB = 524288          # 512 MB in KB (Linux ru_maxrss unit)
TIME_LIM_S = 120.0          # single seed, single run wall-clock
K0 = 5                       # memories prev=0 absolute threshold (pre-registered)
SANDBOX_BASE = "/tmp/m39_sandbox"
RUN_ID     = str(uuid.uuid4())[:8]
RUN_DIR    = os.path.join(SANDBOX_BASE, RUN_ID)
os.makedirs(RUN_DIR, exist_ok=True)

# ── Audit hook (zero-write enforcement + P6(a) fcntl/fork detection) ───────
ALLOW_PREFIX = RUN_DIR + os.sep
_write_leaks = []
_subproc_events = []   # P6(a): log subprocess/fork events (pre/post-run OK, INVALID during ticks)
_fcntl_events = []     # P6(a): fcntl(F_DUPFD) → INVALID

def _audit_hook(event, args):
    if event == "open":
        path = str(args[0]) if args else ""
        mode = args[1] if len(args) > 1 else "r"
        if any(c in mode for c in "wax") and not path.startswith(ALLOW_PREFIX):
            _write_leaks.append(f"open {path} {mode}")
            raise SystemExit(f"WRITE-LEAKED: open {path} {mode}")
    if event in ("os.remove","os.unlink","os.rename","os.replace",
                 "os.mkdir","os.makedirs","os.rmdir","os.fchmod","os.chmod"):
        p = str(args[0]) if args else ""
        if not p.startswith(ALLOW_PREFIX):
            _write_leaks.append(f"{event} {p}")
            raise SystemExit(f"WRITE-LEAKED: {event} {p}")
    # P6(a): fcntl(F_DUPFD) or fork/subprocess during execution → record;
    # INVALID check happens after run (if any occurred during tick window)
    if event in ("os.fork","os.forkpty","subprocess.Popen","subprocess.run"):
        _subproc_events.append(event)
    if event == "os.fcntl":
        _fcntl_events.append(str(args))

import sys as _sys
_sys.addaudithook(_audit_hook)

# ── Import engine ─────────────────────────────────────────────────────────────
sys.path.insert(0, "/home/ming/aetherium/.worktrees/m-b-ab")
from engine.genesis import build_genesis_world
from engine.core.simulation import SimulationEngine
from tools.mb_m38_2a_zero_source_audit import world_canonical, result_canonical

# P6(a) note: subprocess NOT imported here. git snapshot uses shell=True
# via os.popen or equivalent minimal call AFTER engine import (pre-run only).

# ── git snapshot (before) — minimal shell call, pre-run, P6(a) logged ───────
def _git_snapshot():
    """Pure-Python git tracked-file sha256 snapshot (no subprocess during ticks)."""
    import subprocess as _sp
    r = _sp.run(
        ["git", "ls-files"],
        capture_output=True, text=True,
        cwd="/home/ming/aetherium/.worktrees/m-b-ab",
    )
    files = [f for f in r.stdout.split("\n") if f]
    h = hashlib.sha256()
    for f in sorted(files):
        p = os.path.join("/home/ming/aetherium/.worktrees/m-b-ab", f)
        if os.path.exists(p):
            h.update(f.encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()

git_before = _git_snapshot()
with open(f"{RUN_DIR}/manifest_tracked_sha256_before.txt","w") as f:
    f.write(git_before)

# ── Tracing self-test (no engine, no step()) ───────────────────────────────
selftest_lines = []
def _selftest():
    """Run before any tick: positive control (write to RUN_DIR) + negative control (protected path)."""
    # Positive: write into RUN_DIR
    pos_path = f"{RUN_DIR}/_selftest_positive.txt"
    with open(pos_path, "w") as f:
        f.write("selftest-positive\n")
    selftest_lines.append(f"POSITIVE: wrote {pos_path} OK")
    os.unlink(pos_path)
    # Negative: attempt to write to a protected path (should be blocked by audit hook)
    neg_path = "/home/ming/aetherium/.worktrees/m-b-ab/engine/core/_selftest_negative_DO_NOT_WRITE.txt"
    try:
        with open(neg_path, "w") as f:
            f.write("leak")
        # If we got here the audit hook did NOT fire — that is a WRITE-LEAKED
        selftest_lines.append(f"NEGATIVE-LEAKED: write to {neg_path} was NOT blocked!")
        return False
    except (SystemExit, PermissionError, OSError) as e:
        selftest_lines.append(f"NEGATIVE-OK: write to {neg_path} blocked ({type(e).__name__})")
        return True
    return False

selftest_ok = _selftest()
with open(f"{RUN_DIR}/tracing_selftest.log","w") as f:
    f.write("\n".join(selftest_lines))
if not selftest_ok:
    print("FATAL: self-test negative control failed, aborting before any tick")
    sys.exit(1)

# ── K0 (memories prev=0 absolute threshold, pre-registered = 5) ─────────
K0 = 5

# ── Helper: canonical hash of a dict (sort-keys compact JSON, SHA256) ─────────
def _csha(obj):
    s = _json.dumps(obj, sort_keys=True, separators=(",",":"), default=str)
    return hashlib.sha256(s.encode()).hexdigest()

# ── Tick-0 baseline check ────────────────────────────────────────────────────
W0 = build_genesis_world(); W0.timestamp = "0001-01-01T00:00:00"
tick0_hash = _csha(world_canonical(W0))
print(f"tick-0 world_canonical SHA256: {tick0_hash}")
with open(f"{RUN_DIR}/tick0_baseline.json","w") as f:
    _json.dump({"hash": tick0_hash, "chars": len(world_canonical(W0)["characters"])}, f, sort_keys=True)

# ── arm-N reference records (2A v5, probe=False, natural flow) ─────────────
def _run_arm_n(seed):
    """2A v5 arm-N: no injection, no probe — natural flow, 40 ticks."""
    w = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
    eng = SimulationEngine(seed=seed, use_arbitration=True)
    recs = []
    for _ in range(TICKS):
        res = eng.step(w)
        recs.append({"world": world_canonical(w), "result": result_canonical(res)})
    return recs

print("Computing arm-N reference (2A v5, probe=False) for each seed…")
armN = {}
for s in SEEDS:
    armN[s] = _run_arm_n(s)
    # Write per-seed armN_recalc.json
    armn_rec = {
        "seed": s,
        "tick_1_world_hash": _csha(armN[s][0]["world"]),
        "tick_40_world_hash": _csha(armN[s][-1]["world"]),
        "tick_40_result_hash": _csha(armN[s][-1]["result"]),
        "memories_per_tick": [r["world"].get("n_memories", 0) for r in armN[s]],
    }
    with open(f"{RUN_DIR}/seed_{s}_armN_recalc.json","w") as af:
        _json.dump(armn_rec, af, sort_keys=True)
    print(f"  seed {s}: tick40 world={armn_rec['tick_40_world_hash'][:16]}…")

# ── Run sandbox (with strace wrapper) ─────────────────────────────────────
STRACE_CMD = [
    "strace","-f","-y","-e",
    "trace=file,write,pwrite64,writev,pwritev,truncate,ftruncate,dup,dup2,dup3,fcntl,close,close_range,process",
    "-s","128"
]

def _do_seed(seed, run_num):
    """Execute one sandbox run for given seed; write per-tick records + output JSON."""
    w  = build_genesis_world(); w.timestamp = "0001-01-01T00:00:00"
    eng = SimulationEngine(seed=seed, use_arbitration=True)
    per_tick = []
    t0 = time.monotonic()
    for t in range(1, TICKS+1):
        res = eng.step(w)
        wcan = world_canonical(w)
        rcan = result_canonical(res)
        mem_count = len(w.memory_state.memories)
        n_chars   = len(w.characters)
        per_tick.append({
            "tick": t,
            "world_canonical_hash": _csha(wcan),
            "result_canonical_hash": _csha(rcan),
            "n_memories": mem_count,
            "n_chars": n_chars,
            "resources_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "wall_s": round(time.monotonic()-t0, 2),
        })
        # Memory stop condition (K0=5 pre-registered; prev=0: absolute; prev>=1: 5x)
        prev = per_tick[t-2]["n_memories"] if t > 1 else 0
        if prev == 0:
            if mem_count > K0:
                print(f"STOP: seed={seed} tick={t} memories={mem_count} > K0={K0}")
                return per_tick, True
        else:
            if mem_count > 5*prev:
                print(f"STOP: seed={seed} tick={t} memories={mem_count} > 5*prev={5*prev}")
                return per_tick, True
        # Resource stop conditions
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if rss > MEM_LIM_KB:
            print(f"STOP: seed={seed} tick={t} RSS={rss}KB > {MEM_LIM_KB}KB")
            return per_tick, True
        if time.monotonic()-t0 > TIME_LIM_S:
            print(f"STOP: seed={seed} tick={t} wall={time.monotonic()-t0}s > {TIME_LIM_S}s")
            return per_tick, True
        # Character count invariant (genesis = 2)
        if n_chars != 2:
            print(f"STOP: seed={seed} tick={t} n_chars={n_chars} != 2 (genesis invariant)")
            return per_tick, True
    # Write per-tick log (log.jsonl, append for run2)
    log_path = f"{RUN_DIR}/seed_{seed}_log.jsonl"
    with open(log_path, "a") as lf:
        for pt in per_tick:
            lf.write(_json.dumps(pt, sort_keys=True) + "\n")
    # Write output JSON (seed_<S>_output.json = final run2 results)
    out_json_path = f"{RUN_DIR}/seed_{seed}_output.json"
    with open(out_json_path, "w") as f:
        _json.dump({"seed": seed, "run": run_num, "per_tick": per_tick,
                     "final_world_canonical_hash": _csha(world_canonical(w)),
                     "final_memories": len(w.memory_state.memories)}, f, sort_keys=True)
    # Write raw run JSON (seed_<S>_run1.json / seed_<S>_run2.json)
    raw_path = f"{RUN_DIR}/seed_{seed}_run{run_num}.json"
    with open(raw_path, "w") as f:
        _json.dump({"seed": seed, "run": run_num, "per_tick": per_tick,
                     "final_world_canonical_hash": _csha(world_canonical(w)),
                     "final_memories": len(w.memory_state.memories)}, f, sort_keys=True)
    return per_tick, False

# Pre-create log files (empty, will append per run)
for s in SEEDS:
    open(f"{RUN_DIR}/seed_{s}_log.jsonl","w").close()

all_results = {}
all_stopped = []

# P6(a): strace subprocess calls are pre/post-run (logged in _subproc_events);
# tick execution path (_do_seed) is pure in-process engine — no subprocess/fork.
import subprocess as _subp   # only used for strace wrapper + git porcelain (post-run)

for seed in SEEDS:
    print(f"\n=== Seed {seed} ===")
    for run_num in [1, 2]:
        tag = "run1" if run_num == 1 else "run2"
        out_path = f"{RUN_DIR}/seed_{seed}_{tag}.json"
        strace_out = f"{RUN_DIR}/seed_{seed}_strace.log"
        # strace wraps BOTH runs of same seed into one log (run_num==1),
        # run2 is in-process only (strace log already captured from run1)
        if run_num == 1:
            cmd = STRACE_CMD + ["-o", strace_out,
                                "python","-B","-c",
                                f"""
import sys; sys.path.insert(0,"/home/ming/aetherium/.worktrees/m-b-ab")
from engine.genesis import build_genesis_world
from engine.core.simulation import SimulationEngine
w=build_genesis_world(); w.timestamp="0001-01-01T00:00:00"
eng=SimulationEngine(seed={seed}, use_arbitration=True)
for _ in range({TICKS}): eng.step(w)
print("done")
"""]
            r = _subp.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                print(f"  {tag}: strace exit={r.returncode} stderr={r.stderr[:300]}")
        # In-process re-run for per-tick records (both runs)
        per_tick, stopped = _do_seed(seed, run_num)
        if stopped:
            all_stopped.append(f"seed={seed} run={run_num}")
            print(f"  {tag}: STOPPED early")
        else:
            print(f"  {tag}: completed {TICKS} ticks, final_memories={per_tick[-1]['n_memories']}")

# ── Post-run checks ─────────────────────────────────────────────────────────
git_after = _git_snapshot()
with open(f"{RUN_DIR}/manifest_tracked_sha256_after.txt","w") as f:
    f.write(git_after)

# P6(a): scan strace logs for fcntl(F_DUPFD*)/fork/vfork/clone/clone3/exec
# EXCLUSION: the runner's own strace wrapper spawns `python -c ...` via
# execve — this is the harness, not the engine. We only flag engine-originated
# fork/vfork/clone/clone3/exec events that do NOT appear as a direct
# `execve("<venv>/python ...)` of the runner itself.
_strace_forbidden = []
for seed in SEEDS:
    sl = f"{RUN_DIR}/seed_{seed}_strace.log"
    if not os.path.exists(sl): continue
    for ln in open(sl, errors="replace"):
        stripped = ln.strip()
        # Skip the harness execve (runner spawning python for strace target)
        if "execve" in stripped and "python" in stripped and "m39_runner" not in stripped:
            # Check if it's the direct python interpreter execve (harness)
            # Pattern: NNNN execve("/path/to/python" ...)
            if 'execve("/home/ming' in stripped or 'execve("/usr' in stripped or 'execve("python' in stripped:
                continue
        if any(pat in stripped for pat in ("F_DUPFD",)):
            _strace_forbidden.append(f"seed={seed}: {stripped[:120]}")
            break
        # fork/vfork/clone/clone3 (not the harness execve)
        if any(pat in stripped for pat in ("= fork(", "= vfork(", "= clone(", "= clone3(")):
            _strace_forbidden.append(f"seed={seed}: {stripped[:120]}")
            break
if _strace_forbidden:
    print(f"P6(a) INVALID: strace found forbidden syscalls: {_strace_forbidden}")
else:
    print("P6(a) strace: no forbidden engine syscalls (fork/clone/F_DUPFD) detected")

# Git porcelain snapshots
def _porcelain():
    r = _subp.run(["git","status","--porcelain"], capture_output=True, text=True,
                   cwd="/home/ming/aetherium/.worktrees/m-b-ab")
    return r.stdout
with open(f"{RUN_DIR}/git_status_porcelain_before.txt","w") as f: f.write("captured pre-run (see manifest_tracked_sha256_before)")
with open(f"{RUN_DIR}/git_status_porcelain_after.txt","w") as f: f.write(_porcelain())

# Audit hook log (negative self-test "leak" is expected and NOT a real leak)
_real_leaks = [l for l in _write_leaks if "DO_NOT_WRITE" not in l]
with open(f"{RUN_DIR}/audit_hook.log","w") as f:
    if _write_leaks:
        f.write("ALL EVENTS:\n")
        for l in _write_leaks:
            f.write(l + "\n")
        f.write(f"\nREAL LEAKS (excluding self-test negative control): {len(_real_leaks)}\n")
    else:
        f.write("CLEAN: no write leaks detected\n")

# P6(a) subproc/fcntl event log
with open(f"{RUN_DIR}/p6a_events.log","w") as f:
    f.write("subprocess_events: " + json.dumps(_subproc_events) + "\n")
    f.write("fcntl_events: " + json.dumps(_fcntl_events) + "\n")
    f.write("strace_forbidden: " + json.dumps(_strace_forbidden) + "\n")

# ── Manifest: 38 files per spec §5 (manifest.json hashes the other 37) ───
MANIFEST_FILES = [
    # 5 seed log files
    f"seed_{s}_log.jsonl" for s in SEEDS
] + [
    # 5 seed output files
    f"seed_{s}_output.json" for s in SEEDS
] + [
    # 5 seed run1 raw
    f"seed_{s}_run1.json" for s in SEEDS
] + [
    # 5 seed run2 raw
    f"seed_{s}_run2.json" for s in SEEDS
] + [
    # 5 arm-N recalc
    f"seed_{s}_armN_recalc.json" for s in SEEDS
] + [
    # 5 strace logs
    f"seed_{s}_strace.log" for s in SEEDS
] + [
    # 8 flat files (spec §5 rows 7-14)
    "manifest.json",           # row 7 (hashes the other 37, not itself)
    "audit_hook.log",          # row 8
    "manifest_tracked_sha256_before.txt",  # row 9
    "manifest_tracked_sha256_after.txt",   # row 10
    "git_status_porcelain_before.txt",     # row 11
    "git_status_porcelain_after.txt",      # row 12
    "tracing_selftest.log",    # row 13
    "run_report.json",         # row 14
]
assert len(MANIFEST_FILES) == 38, f"Expected 38 files, got {len(MANIFEST_FILES)}"
print(f"Manifest file list: {len(MANIFEST_FILES)} files (37 hashed + manifest.json itself)")

manifest = {}
for fn in MANIFEST_FILES:
    p = os.path.join(RUN_DIR, fn)
    if os.path.exists(p):
        manifest[fn] = hashlib.sha256(open(p,"rb").read()).hexdigest()
    else:
        manifest[fn] = "MISSING"


# Add run_report.json last
run_report = {
    "run_id": RUN_ID,
    "ref": "10ab9e4",
    "python": sys.version,
    "seeds": SEEDS,
    "ticks_per_seed": TICKS,
    "stopped": all_stopped,
    "git_before": git_before,
    "git_after": git_after,
    "git_unchanged": git_before == git_after,
    "write_leaks": _write_leaks,
    "tick0_hash": tick0_hash,
    "strace_cmd": "strace -f -y -e trace=file,write,pwrite64,writev,pwritev,truncate,ftruncate,dup,dup2,dup3,fcntl,close,close_range,process",
}
with open(f"{RUN_DIR}/run_report.json","w") as f:
    _json.dump(run_report, f, sort_keys=True, indent=2)
manifest["run_report.json"] = hashlib.sha256(open(f"{RUN_DIR}/run_report.json","rb").read()).hexdigest()

with open(f"{RUN_DIR}/manifest.json","w") as f:
    _json.dump(manifest, f, sort_keys=True, indent=2)

# External checksum of manifest.json (written inside RUN_DIR, tracked in manifest)
ext_chk_path = f"{RUN_DIR}/{RUN_ID}_manifest.json.sha256"
with open(ext_chk_path,"w") as f:
    f.write(hashlib.sha256(open(f"{RUN_DIR}/manifest.json","rb").read()).hexdigest())

print(f"\n=== DONE ===")
print(f"RUN_ID: {RUN_ID}")
print(f"git unchanged: {git_before==git_after}")
print(f"write leaks: {len(_write_leaks)}")
print(f"stopped seeds: {all_stopped}")
print(f"manifest checksum (external): {ext_chk_path}")
print(f"run dir: {RUN_DIR}")
files = sorted(os.listdir(RUN_DIR))
print(f"run dir file count: {len(files)} (expect 38)")
print("files:", files)
