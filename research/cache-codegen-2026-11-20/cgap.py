"""Cached executables under code generation variants: build each program's program-cache
executable once per variant (the driver's PYSTACHY_X_PCCOMPILE experiment hook, scratch trees
only), then run the executables interleaved, pinned to CPU 1, and compare.

usage: cgap.py TREE ROUNDS OUT.json [PROGRAM...]
Every variant's stdout must equal the first's. Records wall seconds, the program's own
"seconds X" line (pyperformance) and knn=/layout= stage timers (UMAP probe).
"""
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

SP = "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad"
W = f"{SP}/cgap"
tree, rounds, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
only = sys.argv[4:]
CC = "clang -O2 -Xclang -disable-llvm-passes -mllvm -profile-guided-section-prefix=false -fPIC"
VARIANTS = {
    "clang": "",
    "nobypass": f"{CC} -Xclang -target-feature -Xclang -idivq-to-divl -c {{bc}} -o {{obj}}",
    "llc": "llc -O2 -relocation-model=pic -filetype=obj {bc} -o {obj}",
    "al32": f"{CC} -falign-loops=32 -c {{bc}} -o {{obj}}",
    "nb-al32": f"{CC} -Xclang -target-feature -Xclang -idivq-to-divl -falign-loops=32 -c {{bc}} -o {{obj}}",
    "al64": f"{CC} -falign-loops=64 -c {{bc}} -o {{obj}}",
    "in64": f"{CC} -mllvm -x86-experimental-pref-innermost-loop-alignment=6 -c {{bc}} -o {{obj}}",
    "in32": f"{CC} -mllvm -x86-experimental-pref-innermost-loop-alignment=5 -c {{bc}} -o {{obj}}",
}
AOT = os.getenv("CGAP_MODE", "") == "aot"
if AOT:
    VARIANTS = {"aot": "", "aot-nobypass": " -Xclang -target-feature -Xclang -idivq-to-divl"}
if os.getenv("CGAP_VARIANTS"):
    VARIANTS = {k: v for k, v in VARIANTS.items() if k in os.getenv("CGAP_VARIANTS").split(",")}
PP = {
    "barnes_hut": ["1"], "bpe_tokeniser": ["1"], "chaos": ["10"], "comprehensions": ["10000"],
    "fannkuch": ["2"], "float": ["10"], "generators": ["10"], "go": ["4"], "hexiom": ["100"],
    "json_dumps": ["20"], "json_loads": ["2000"], "bm_logging": ["32"], "meteor_contest": ["6"],
    "nbody": ["10"], "nqueens": ["10"], "pidigits": ["4"], "raytrace": ["4"], "regex_dna": ["4"],
    "regex_effbot": ["20"], "regex_v8": ["20"], "richards": ["20"], "richards_super": ["20"],
    "scimark": ["2"], "spectral_norm": ["10"], "unpack_sequence": ["50000"],
}
PROGRAMS = {"umap": (f"{SP}/probe/umap_core.py", ["10000", "16", "10", "15", "200", "7"]),
            "divmicro": (f"{W}/divmicro.py", ["7", "20000000"])}
for name, args in PP.items():
    PROGRAMS["pp-" + name] = (f"{tree}/bench/pyperformance/{name}.py", args)
for f in sorted(os.listdir(f"{tree}/bench")):
    if f.endswith(".py"):
        PROGRAMS["b-" + f[:-3]] = (f"{tree}/bench/{f}", [])
if only:
    PROGRAMS = {k: v for k, v in PROGRAMS.items() if k in only}
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
extra = dict(kv.split("=", 1) for kv in os.getenv("CGAP_EXTRA", "").split(",") if kv)  # (build-time settings, e.g. PYSTACHY_JIT_CPU=generic)
exes = {}
RUNNER = os.getenv("CGAP_RUNNER", "") == "1"
for prog, (src, args) in PROGRAMS.items():
    if RUNNER:
        exes[(prog, "runner")] = None
    for var, cc in VARIANTS.items():
        cache = f"{W}/pc/{os.path.basename(tree)}/{var}/{prog}"
        if AOT:
            exe = f"{cache}/{prog}.exe"
            if not os.path.exists(exe):
                os.makedirs(cache, exist_ok=True)
                env = base | extra | {"PYSTACHY_CACHE": cache} | ({"PYSTACHY_X_AOTFLAGS": cc} if cc else {})
                p = subprocess.run([f"{tree}/pystachy", "build", src, "-o", exe], env=env, cwd=tree, capture_output=True, stdin=subprocess.DEVNULL)
                if p.returncode or not os.path.exists(exe):
                    print(f"{prog} {var}: build exit {p.returncode}: {p.stderr.decode()[-300:]}", flush=True)
                    continue
            exes[(prog, var)] = exe
            continue
        # a stable copy per program and variant; built in one cache per variant (one runtime build),
        # the new executable being the one that was not there before
        stable = f"{W}/exe/{os.path.basename(tree)}/{var}/{prog}.exe"
        old = [f for f in os.listdir(cache + "/program-v2") if f.endswith(".exe")] if os.path.isdir(cache + "/program-v2") else []
        if not os.path.exists(stable):
            os.makedirs(os.path.dirname(stable), exist_ok=True)
            if len(old) == 1:
                shutil.copy2(f"{cache}/program-v2/{old[0]}", stable)
            else:
                shared = f"{W}/pc/{os.path.basename(tree)}/{var}/_shared"
                pv = shared + "/program-v2"
                before = set(f for f in os.listdir(pv) if f.endswith(".exe")) if os.path.isdir(pv) else set()
                env = base | extra | {"PYSTACHY_CACHE": shared, "PYSTACHY_PROGRAM_CACHE_TRACE": "1"} | ({"PYSTACHY_X_PCCOMPILE": cc} if cc else {})
                p = subprocess.run([f"{tree}/pystachy", "run", src, *args], env=env, cwd=tree, capture_output=True, stdin=subprocess.DEVNULL)
                new = sorted(set(f for f in os.listdir(pv) if f.endswith(".exe")) - before) if os.path.isdir(pv) else []
                if p.returncode or len(new) != 1 or b"program cache: stored" not in p.stderr:
                    print(f"{prog} {var}: exit {p.returncode}, {len(new)} new executables: {p.stderr.decode()[-300:]}", flush=True)
                    continue
                shutil.copy2(f"{pv}/{new[0]}", stable)
        exes[(prog, var)] = stable
print(f"{len(exes)} executables", flush=True)
runs = {f"{p}|{v}": [] for (p, v) in exes}
names = list(VARIANTS) + (["runner"] if RUNNER else [])
for r in range(rounds):
    for prog, (src, args) in PROGRAMS.items():
        order = names[r % len(names):] + names[:r % len(names)]
        ref = None
        for var in order:
            if (prog, var) not in exes:
                continue
            t0 = time.perf_counter()
            if exes[(prog, var)] is None:
                p = subprocess.run([f"{tree}/pystachy", "run", src, *args], env=base | extra | {"PYSTACHY_PROGRAM_CACHE": "0"}, cwd=tree,
                                   capture_output=True, stdin=subprocess.DEVNULL, preexec_fn=lambda: os.sched_setaffinity(0, {1}))
            else:
                # (argv[0] the source, as cached_run.execute runs it)
                p = subprocess.run([src, *args], executable=exes[(prog, var)], env=base, cwd=tree, capture_output=True,
                                   stdin=subprocess.DEVNULL, preexec_fn=lambda: os.sched_setaffinity(0, {1}))
            wall = time.perf_counter() - t0
            if p.returncode:
                sys.exit(f"{prog} {var}: exit {p.returncode}: {p.stderr.decode()[-300:]}")
            if ref is None:
                ref = p.stdout
            elif p.stdout != ref:
                sys.exit(f"{prog} {var}: stdout differs")
            err = p.stderr.decode()
            row = {"wall": wall} | {k: float(x) for k, x in re.findall(r"\b(knn|layout)=([0-9]+\.[0-9]+)", err)}
            m = re.findall(r"^seconds ([0-9.e-]+)$", err, flags=re.M)
            if m:
                row["seconds"] = sum(float(x) for x in m)
            runs[f"{prog}|{var}"].append(row)
    print(f"round {r} done", flush=True)
json.dump({"tree": tree, "extra": extra, "variants": VARIANTS, "rounds": rounds, "runs": runs}, open(out, "w"), indent=1)
first = names[0]
for prog in PROGRAMS:
    for var in names:
        key = f"{prog}|{var}"
        if not runs.get(key) or not runs.get(f"{prog}|{first}"):
            continue
        for k in sorted(runs[key][0]):
            med = statistics.median(row[k] for row in runs[key])
            paired = statistics.median(a[k] / b[k] for a, b in zip(runs[key], runs[f"{prog}|{first}"], strict=True) if b[k] > 0)
            print(f"{prog:24} {var:9} {k:8} median {med:8.4f}  paired/{first} {paired:.3f}", flush=True)
