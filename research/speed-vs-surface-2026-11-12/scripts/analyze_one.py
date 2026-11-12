"""Per-commit surface and correctness analysis (no timing): CPython-method sweep, upstream
pyperformance census (compile only) and AOT/JIT builds of the frozen perf suite with output checks.

usage: python3.13 -I analyze_one.py LABEL
Reads $S/wt/LABEL (built), writes $S/results/{methods,census,perfprep}-LABEL.json and
AOT executables to $S/exe/LABEL/.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

S = Path("/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad")
SW = S / "sweep"


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    return env


def run(cmd, cwd, timeout, env):
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "", "timeout", time.monotonic() - t0
    return (p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace"),
            time.monotonic() - t0)


def first_error(text, strip=""):
    for line in text.splitlines():
        if ": error: " in line:
            line = re.sub(r" \((compiling|specializing) .*$", "", line)
            return re.sub(r"^.*?/([^/]+\.py):\d+: ", r"\1: ", line.replace(strip, ""))[:300]
    lines = [x for x in text.strip().splitlines() if x.strip()]
    return lines[-1][:300] if lines else ""


def census(wt, env):
    rows = {}
    for d in sorted((SW / "census").iterdir()):
        src = d / f"bm_{d.name}.py"
        rc, out, err, wall = run([str(wt / "pystachy"), "ir", str(src), "-o", os.devnull], wt, 300, env)
        status = "timeout" if rc is None else "compiled" if rc == 0 else "error"
        rows[d.name] = {"status": status, "first_error": "" if rc == 0 else first_error(out + err),
                        "seconds": round(wall, 2)}
    return rows


def seconds_line(stderr):
    found = re.findall(r"^seconds (\S+)$", stderr, re.M)
    return float(found[0]) if len(found) == 1 else None


def perfprep(label, wt, env):
    specs = json.load(open(SW / "perf_specs.json"))
    ref = json.load(open(SW / "cpython_ref.json"))["ref"]
    exedir = S / "exe" / label
    exedir.mkdir(parents=True, exist_ok=True)
    root = SW / "perfroot"
    rows = {}
    for name, spec in specs.items():
        src = str(root / spec["src"])
        exe = exedir / name
        row = {}
        rc, out, err, wall = run([str(wt / "pystachy"), "build", src, "-o", str(exe)], wt, 600, env)
        row["aot_build"] = "timeout" if rc is None else "ok" if rc == 0 and exe.exists() else "error"
        row["aot_build_s"] = round(wall, 2)
        if row["aot_build"] != "ok":
            row["aot_error"] = first_error(out + err)
        else:
            row["exe_bytes"] = exe.stat().st_size
            rc, out, err, wall = run([str(exe)] + spec["args"], root, 300, env)
            row["aot_rc"] = rc
            row["aot_correct"] = rc == 0 and out == ref[name]["stdout"]
            row["aot_wall_s"] = round(wall, 3)
            row["aot_loop_s"] = seconds_line(err) if rc == 0 else None
            if not row["aot_correct"]:
                row["aot_mismatch"] = (out[-200:] + " | " + err[-300:]).strip()
        rc, out, err, wall = run([str(wt / "pystachy"), "run", src] + spec["args"], wt, 600, env)
        row["jit_rc"] = rc
        row["jit_correct"] = rc == 0 and out == ref[name]["stdout"]
        row["jit_wall_s"] = round(wall, 3)
        if not row["jit_correct"]:
            row["jit_error"] = first_error(out + err) if rc not in (0, None) else (out[-200:] + " | " + err[-200:])
        rows[name] = row
    return rows


def main():
    label = sys.argv[1]
    wt = S / "wt" / label
    env = clean_env()
    res = S / "results"
    t0 = time.monotonic()
    subprocess.run([sys.executable, "-I", str(SW / "method_sweep.py"), str(wt), str(SW / "qualified.json"),
                    str(res / f"methods-{label}.json"), "-j", "2"], check=False)
    t1 = time.monotonic()
    json.dump(census(wt, env), open(res / f"census-{label}.json", "w"), indent=1)
    t2 = time.monotonic()
    pp = perfprep(label, wt, env)
    json.dump(pp, open(res / f"perfprep-{label}.json", "w"), indent=1)
    t3 = time.monotonic()
    ok_aot = sum(1 for r in pp.values() if r.get("aot_correct"))
    ok_jit = sum(1 for r in pp.values() if r.get("jit_correct"))
    print(f"{label}: methods {t1 - t0:.0f}s census {t2 - t1:.0f}s perfprep {t3 - t2:.0f}s; "
          f"aot-correct {ok_aot}/{len(pp)} jit-correct {ok_jit}/{len(pp)}", flush=True)


if __name__ == "__main__":
    main()
