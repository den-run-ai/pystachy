"""Callgrind instruction counts (Ir) of the AOT benchmark executables per LLVM version."""
import json, re, subprocess, sys
D = "/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/llvmver.NWwbC2"
TREE = "/home/user/wt/llvm-versions"
BENCH = {"regex_effbot_20": ["20"], "nbody_10": ["10"], "richards_20": ["20"], "json_dumps_20": ["20"],
         "json_loads_2000": ["2000"], "spectral_norm_10": ["10"], "raytrace_4": ["4"], "json_repair_bench_200": ["200", "5", "2"]}
out = {}
for name, args in BENCH.items():
    out[name] = {}
    for n in ["18", "20", "22", "23"]:
        r = subprocess.run(["valgrind", "--tool=callgrind", f"--callgrind-out-file={D}/cg/{name}-{n}.out", f"{D}/speed/{name}-{n}"] + args,
                           cwd=TREE, capture_output=True, text=True)
        m = re.search(r"Collected : (\d+)", r.stderr)
        out[name][n] = int(m.group(1)) if m and r.returncode == 0 else None
    base = out[name]["18"]
    print(name, " ".join(f"{n}={v} ({100 * (v / base - 1):+.2f}%)" for n, v in out[name].items()), flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
