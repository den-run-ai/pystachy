"""LLVM version timing harness (run under scratchpad/timing.sh, pinned to one CPU).

usage: python3.13 -I vbench.py SESSION OUT.json [ROUNDS]
  jit    cold `pystachy run`, program cache off: ORC (default), llc -O0 + ORC load, MCJIT -O0
  miss   program cache on: a miss after an edit (fresh source bytes), then the hit that follows
  aot    `pystachy build` time
  speed  run the AOT benchmark executables built by `vbench.py prepare-speed`
  prepare-speed  build the benchmark executables per version (not timed; run under heavy.sh)
Every timed run's stdout is compared with CPython 3.13's before it counts.
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

D = "/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/llvmver.NWwbC2"
TREE = "/home/user/wt/llvm-versions"
P = TREE + "/pystachy"
W = D + "/w"
CPU = "2"
VERSIONS = os.environ.get("VBENCH_VERSIONS", "18,20,22,23").split(",")
WORKLOADS = {
    "import_heavy": ["import_heavy.py"],
    "regex_effbot_1": ["regex_effbot.py", "1"],
    "route_3000": ["route.py", "rules.txt", "events.tsv"],
}
# AOT benchmark subset: name -> (source, args, PYSTACHY_PATH or "")
BENCH = {
    "regex_effbot_20": ("bench/pyperformance/regex_effbot.py", ["20"], ""),
    "nbody_10": ("bench/pyperformance/nbody.py", ["10"], ""),
    "richards_20": ("bench/pyperformance/richards.py", ["20"], ""),
    "json_dumps_20": ("bench/pyperformance/json_dumps.py", ["20"], ""),
    "json_loads_2000": ("bench/pyperformance/json_loads.py", ["2000"], ""),
    "spectral_norm_10": ("bench/pyperformance/spectral_norm.py", ["10"], ""),
    "raytrace_4": ("bench/pyperformance/raytrace.py", ["4"], ""),
    "json_repair_bench_200": ("bench/json_repair/bench.py", ["200", "5", "2"], "ports"),
}


def env_for(n, llvm=None, extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYSTACHY_LLVM"] = llvm or f"/usr/lib/llvm-{n}/bin"
    env["PYSTACHY_CACHE"] = f"{D}/cache-{n}"
    env["TMPDIR"] = D + "/tmp"
    env["WRAP_TMP"] = D + "/wraptmp"
    env.update(extra or {})
    return env


def timed(cmd, env, cwd):
    t = time.perf_counter()
    r = subprocess.run(["taskset", "-c", CPU] + cmd, cwd=cwd, env=env, capture_output=True)
    return time.perf_counter() - t, r


def cpython(args, cwd, path=""):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    if path:
        env["PYTHONPATH"] = path
    return subprocess.run(["python3.13"] + args, cwd=cwd, env=env, capture_output=True).stdout


def strip_seconds(out):
    return b"\n".join(x for x in out.split(b"\n") if not x.startswith((b"seconds", b"warmup_seconds")))


def summarize(times):
    return {"median_ms": round(statistics.median(times) * 1000, 1), "min_ms": round(min(times) * 1000, 1),
            "max_ms": round(max(times) * 1000, 1), "samples_s": times}


def rotate(items, i):
    k = i % len(items)
    return items[k:] + items[:k]


def session_jit(rounds):
    modes = {
        "orc": lambda n: env_for(n, extra={"PYSTACHY_PROGRAM_CACHE": "0"}),
        "llc_O0_orc": lambda n: env_for(n, llvm=f"{D}/llcwrap-{n}/bin", extra={"PYSTACHY_PROGRAM_CACHE": "0", "LLI_MODE": "llcO0"}),
        "mcjit_O0": lambda n: env_for(n, extra={"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_JIT_CODEGEN": "0"}),
        # experimental: lli's ORC with FastISel forced (codegen stays at -O2 otherwise)
        "orc_fastisel": lambda n: env_for(n, llvm=f"{D}/llcwrap-{n}/bin", extra={"PYSTACHY_PROGRAM_CACHE": "0", "LLI_EXTRA": "-fast-isel"}),
        "orc_fastisel_fastra": lambda n: env_for(n, llvm=f"{D}/llcwrap-{n}/bin", extra={"PYSTACHY_PROGRAM_CACHE": "0", "LLI_EXTRA": "-fast-isel -regalloc=fast"}),
    }
    pick = os.environ.get("VBENCH_JIT_MODES", "orc,llc_O0_orc,mcjit_O0").split(",")
    variants = [(n, m) for n in VERSIONS for m in pick]
    out = {}
    for wl, args in WORKLOADS.items():
        expected = cpython(args, W)
        times = {f"{n}/{m}": [] for n, m in variants}
        for i in range(rounds + 1):  # round 0 warms the file cache and is discarded
            for n, m in rotate(variants, i):
                dt, r = timed([P, "run"] + args, modes[m](n), W)
                assert r.returncode == 0 and r.stdout == expected, (wl, n, m, r.returncode, r.stderr[-400:])
                if i > 0:
                    times[f"{n}/{m}"].append(dt)
        out[wl] = {k: summarize(v) for k, v in times.items()}
        print(wl, " ".join(f"{k}={out[wl][k]['median_ms']}" for k in times), flush=True)
    return out


def session_miss(rounds):
    out = {}
    for wl, args in WORKLOADS.items():
        expected = cpython(args, W)
        dirs = {}
        for n in VERSIONS:
            d = f"{D}/miss/{n}"
            os.makedirs(d, exist_ok=True)
            for f in os.listdir(W):
                if not os.path.exists(f"{d}/{f}"):
                    shutil.copy(f"{W}/{f}", f"{d}/{f}")
            dirs[n] = d
        miss = {n: [] for n in VERSIONS}
        hit = {n: [] for n in VERSIONS}
        for i in range(rounds + 1):
            for n in rotate(VERSIONS, i):
                src = f"{dirs[n]}/{args[0]}"
                with open(src, "a") as f:
                    f.write(f"# edit {time.time_ns()}\n")
                env = env_for(n, extra={"PYSTACHY_PROGRAM_CACHE_TRACE": "1"})
                dt, r = timed([P, "run"] + args, env, dirs[n])
                assert r.returncode == 0 and r.stdout == expected and b"stored" in r.stderr, (wl, n, r.returncode, r.stderr[-400:])
                dt2, r2 = timed([P, "run"] + args, env, dirs[n])
                assert r2.returncode == 0 and r2.stdout == expected and b"hit" in r2.stderr, (wl, n, r2.returncode, r2.stderr[-400:])
                if i > 0:
                    miss[n].append(dt)
                    hit[n].append(dt2)
        out[wl] = {"miss": {n: summarize(v) for n, v in miss.items()}, "hit": {n: summarize(v) for n, v in hit.items()}}
        print(wl, "miss", " ".join(f"{n}={out[wl]['miss'][n]['median_ms']}" for n in VERSIONS),
              "hit", " ".join(f"{n}={out[wl]['hit'][n]['median_ms']}" for n in VERSIONS), flush=True)
    return out


def session_aot(rounds):
    out = {}
    os.makedirs(f"{D}/aotout", exist_ok=True)
    for wl, args in WORKLOADS.items():
        expected = cpython(args, W)
        times = {n: [] for n in VERSIONS}
        for i in range(rounds + 1):
            for n in rotate(VERSIONS, i):
                exe = f"{D}/aotout/{wl}-{n}"
                dt, r = timed([P, "build", args[0], "-o", exe], env_for(n), W)
                assert r.returncode == 0 and r.stderr == b"", (wl, n, r.returncode, r.stderr[-400:])
                if i == 0:
                    c = subprocess.run([exe] + args[1:], cwd=W, capture_output=True)
                    assert c.returncode == 0 and c.stdout == expected, (wl, n, "aot output differs")
                else:
                    times[n].append(dt)
        out[wl] = {n: summarize(v) for n, v in times.items()}
        print(wl, " ".join(f"{n}={out[wl][n]['median_ms']}" for n in VERSIONS), flush=True)
    return out


def prepare_speed():
    os.makedirs(f"{D}/speed", exist_ok=True)
    info = {}
    for name, (src, args, path) in BENCH.items():
        expected = strip_seconds(cpython([src] + args, TREE, path=f"{TREE}/{path}" if path else ""))
        for n in VERSIONS:
            exe = f"{D}/speed/{name}-{n}"
            extra = {"PYSTACHY_PATH": path} if path else {}
            t = time.perf_counter()
            r = subprocess.run([P, "build", src, "-o", exe], cwd=TREE, env=env_for(n, extra=extra), capture_output=True)
            bt = time.perf_counter() - t
            assert r.returncode == 0 and r.stderr == b"", (name, n, r.stderr[-400:])
            c = subprocess.run([exe] + args, cwd=TREE, capture_output=True)
            same = c.returncode == 0 and strip_seconds(c.stdout) == expected
            info[f"{name}/{n}"] = {"build_s_untimed_session": round(bt, 2), "output_matches_cpython": same,
                                   "size_bytes": os.path.getsize(exe)}
            print(name, n, "build", round(bt, 2), "s, matches CPython:", same, flush=True)
            assert same, (name, n, c.returncode, c.stdout[-300:], c.stderr[-300:])
    return info


def self_seconds(r):
    for line in (r.stderr + b"\n" + r.stdout).split(b"\n"):
        if line.startswith(b"seconds"):
            return float(line.split()[1])
    return None


def session_speed(rounds):
    out = {}
    for name, (src, args, path) in BENCH.items():
        expected = strip_seconds(cpython([src] + args, TREE, path=f"{TREE}/{path}" if path else ""))
        wall = {n: [] for n in VERSIONS}
        own = {n: [] for n in VERSIONS}
        for i in range(rounds + 1):
            for n in rotate(VERSIONS, i):
                exe = f"{D}/speed/{name}-{n}"
                dt, r = timed([exe] + args, dict(os.environ), TREE)
                assert r.returncode == 0 and strip_seconds(r.stdout) == expected, (name, n)
                if i > 0:
                    wall[n].append(dt)
                    if name.startswith("json_repair"):
                        own[n].append(statistics.median(float(x.split()[1]) for x in r.stdout.split(b"\n") if x.startswith(b"seconds")))
                    else:
                        own[n].append(self_seconds(r))
        out[name] = {"wall": {n: summarize(v) for n, v in wall.items()}, "timed_part": {n: summarize(v) for n, v in own.items()}}
        print(name, "timed-part ms", " ".join(f"{n}={out[name]['timed_part'][n]['median_ms']}" for n in VERSIONS), flush=True)
    return out


def stage_times(stderr):
    st = {}
    for line in stderr.decode(errors="replace").split("\n"):
        p = line.split("\t")
        if len(p) == 3 and p[0] == "pystachy-timing":
            st[p[1]] = st.get(p[1], 0.0) + float(p[2])
    return st


def session_stages(rounds):
    # PYSTACHY_TIMING=1 breakdown: JIT (cache off; lli = wall - driver.prepare_run) and AOT build
    os.makedirs(f"{D}/aotout", exist_ok=True)
    out = {}
    for wl, args in WORKLOADS.items():
        expected = cpython(args, W)
        rec = {f"{kind}/{n}": [] for kind in ("jit", "aot") for n in VERSIONS}
        for i in range(rounds + 1):
            for n in rotate(VERSIONS, i):
                env = env_for(n, extra={"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_TIMING": "1"})
                dt, r = timed([P, "run"] + args, env, W)
                assert r.returncode == 0 and r.stdout == expected, (wl, n, r.stderr[-300:])
                st = stage_times(r.stderr)
                st["wall"] = dt
                st["lli_after_prepare"] = dt - st.get("driver.prepare_run", 0.0)
                dt2, r2 = timed([P, "build", args[0], "-o", f"{D}/aotout/{wl}-stages-{n}"], env, W)
                assert r2.returncode == 0, (wl, n, r2.stderr[-300:])
                st2 = stage_times(r2.stderr)
                st2["wall"] = dt2
                if i > 0:
                    rec[f"jit/{n}"].append(st)
                    rec[f"aot/{n}"].append(st2)
        out[wl] = {}
        for k, runs in rec.items():
            keys = sorted(set().union(*[set(x) for x in runs]))
            out[wl][k] = {s: round(statistics.median(x.get(s, 0.0) for x in runs) * 1000, 1) for s in keys}
        print(wl, {k: {s: v for s, v in out[wl][k].items() if s in ("wall", "program.jit_optimize", "lli_after_prepare", "program.optimize_codegen", "program.llvm_optimize", "program.codegen", "program.link", "program.frontend")} for k in out[wl]}, flush=True)
    return out


def session_selfaot(rounds):
    # AOT build of the compiler itself (pystachy.py, ~880k lines of IR). 22/23 need the coro.end
    # rewrite wrapper, which only affects program.llvm_link (it rewrites the .ll llvm-link reads)
    os.makedirs(f"{D}/selfaot", exist_ok=True)
    ref = subprocess.run([P, "ir", f"{W}/import_heavy.py"], cwd=W, env=env_for("18"), capture_output=True).stdout
    rec = {n: [] for n in VERSIONS}
    for i in range(rounds):
        for n in rotate(VERSIONS, i):
            wrapped = n in ("22", "23")
            llvm = f"{D}/corowrap-{n}/bin" if wrapped else None
            env = env_for(n, llvm=llvm, extra={"PYSTACHY_TIMING": "1"})
            if wrapped:
                env["PYSTACHY_CACHE"] = f"{D}/cache-{n}w"
            exe = f"{D}/selfaot/pystachy-{n}"
            dt, r = timed([P, "build", "pystachy.py", "-o", exe], env, TREE)
            assert r.returncode == 0, (n, r.stderr[-400:])
            st = stage_times(r.stderr)
            st["wall"] = dt
            st["coro_wrapper"] = 1.0 if wrapped else 0.0
            same = subprocess.run([exe, "ir", f"{W}/import_heavy.py"], cwd=W, env=env_for("18"), capture_output=True).stdout == ref
            assert same, (n, "self-built compiler emits different IR")
            rec[n].append(st)
            print(n, {k: round(v, 1) for k, v in st.items() if k in ("wall", "program.frontend", "program.llvm_link", "program.llvm_optimize", "program.late_inline", "program.codegen", "program.link")}, flush=True)
    return {n: [{k: round(v * 1000, 1) for k, v in st.items()} for st in runs] for n, runs in rec.items()}


def main():
    session, path = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    if len(sys.argv) > 4:  # optional comma-separated subset of WORKLOADS (or BENCH for speed)
        keep = sys.argv[4].split(",")
        for table in (WORKLOADS, BENCH):
            for k in [k for k in table if k not in keep]:
                if any(x in table for x in keep):
                    del table[k]
    meta = {"session": session, "rounds": rounds, "cpu": CPU, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "compiler": P, "tree_head": subprocess.run(["git", "-C", TREE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "llvm": {n: subprocess.run([f"/usr/lib/llvm-{n}/bin/clang", "--version"], capture_output=True, text=True).stdout.split("\n")[0] for n in VERSIONS},
            "cpython": subprocess.run(["python3.13", "--version"], capture_output=True, text=True).stdout.strip()}
    fn = {"jit": session_jit, "miss": session_miss, "aot": session_aot, "speed": session_speed, "stages": session_stages, "selfaot": session_selfaot}
    if session == "prepare-speed":
        result = prepare_speed()
    else:
        result = fn[session](rounds)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w") as f:
        json.dump({"meta": meta, "results": result}, f, indent=1)


if __name__ == "__main__":
    main()
