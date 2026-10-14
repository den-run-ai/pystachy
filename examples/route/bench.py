"""Compare route.py under CPython and as a Pystachy AOT executable.

usage: python3 -I bench.py PYSTACHY [N] [--json PATH]
Each round alternates CPython/AOT order, measuring the whole program and routing alone.
Every report must agree across runtimes, timing modes and repetitions. Traces, executable
and optional raw timing/provenance JSON go to build/route/ (unless PATH selects elsewhere).
"""
import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


def peak_rss(cmd: list[str], expected: str | None = None) -> tuple[int, str]:
    # Peak RSS of one child, in KiB on Linux (macOS reports bytes).
    probe = "import json, resource, subprocess, sys; p = subprocess.run(sys.argv[1:], capture_output=True, text=True, check=True); print(json.dumps([resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, p.stdout, p.stderr]))"
    raw, report, diagnostics = json.loads(subprocess.run([sys.executable, "-I", "-c", probe] + cmd, capture_output=True, text=True, check=True).stdout)
    if expected is not None and report != expected:
        raise ValueError(f"OUTPUT DIFFERS in RSS run for {cmd!r}:\nexpected:\n{expected}\ngot:\n{report}")
    if diagnostics:
        raise ValueError(f"unexpected RSS run diagnostics for {cmd!r}: {diagnostics!r}")
    return (raw // 1024 if sys.platform == "darwin" else raw), report


def routing_time(stderr: str) -> float:
    fields = stderr.split()
    if len(fields) != 7 or fields[0] != "routing:" or fields[2] != "s," or fields[4:] != ["ns", "per", "event"]:
        raise ValueError(f"invalid routing report: {stderr!r}")
    seconds = float(fields[1])
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"invalid routing duration: {seconds}")
    return seconds


def measure_pair(commands: list[list[str]], runs: int, events: int) -> list[dict]:
    if runs < 1:
        raise ValueError("runs must be positive")
    samples = [{"wall_s": [], "routing_s": []} for _ in commands]
    expected = None
    for round_index in range(runs):
        # Reverse runtime order on alternate rounds, so drift affects both runtimes.
        order = range(len(commands)) if round_index % 2 == 0 else range(len(commands) - 1, -1, -1)
        for index in order:
            cmd = commands[index]
            t = time.perf_counter()
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            samples[index]["wall_s"].append(time.perf_counter() - t)
            for result in [p, subprocess.run(cmd + ["--in-memory"], capture_output=True, text=True, check=True)]:
                if not result.stdout.startswith(f"{events} events, "):
                    raise ValueError(f"event count differs for {cmd!r}: {result.stdout!r}")
                if expected is None:
                    expected = result.stdout
                elif result.stdout != expected:
                    raise ValueError(f"OUTPUT DIFFERS for {cmd!r}, round {round_index + 1}:\nexpected:\n{expected}\ngot:\n{result.stdout}")
            samples[index]["routing_s"].append(routing_time(result.stderr))
            if p.stderr:
                raise ValueError(f"unexpected streaming diagnostics for {cmd!r}: {p.stderr!r}")
    for sample in samples:
        sample["report"] = expected
    return samples


def provenance(root: Path, compiler: str, paths: list[Path]) -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()

    # Follow the compiler's apt/Homebrew discovery, including an explicit empty PATH override.
    probe = "import sys; sys.path.insert(0, sys.argv[1]); import pystachy; print(pystachy.llvm_dir())"
    llvm_dir = subprocess.run([sys.executable, "-I", "-c", probe, str(root)], capture_output=True, text=True, check=True).stdout.strip()
    clang = str(Path(llvm_dir) / "clang") if llvm_dir else "clang"
    settings = ["PYSTACHY_LLVM", "PYSTACHY_OPT", "PYSTACHY_CFLAGS", "PYSTACHY_GC", "PYSTACHY_GC_STRESS", "PYSTACHY_HOME", "PYSTACHY_PATH", "PYSTACHY_JIT_INLINE"]
    cpu_model = platform.processor()
    try:
        cpu_model = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name"))
    except (OSError, StopIteration):
        pass
    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "revision": git("rev-parse", "HEAD"),
        "working_tree_diff": git("diff", "HEAD", "--", "examples/route", "pystachy.py", "src", "runtime.c", "runtime.py", "lib"),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "cpus": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "compiler": compiler,
        "clang": subprocess.run([clang, "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
        "settings": {key: os.environ[key] for key in settings if key in os.environ},
        "sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler")
    parser.add_argument("runs", nargs="?", type=int, default=5)
    parser.add_argument("--json", type=Path, help="save raw rounds and provenance")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("runs must be positive")
    here = Path(__file__).resolve().parent
    root = here.parent.parent
    out = root / "build" / "route"
    out.mkdir(parents=True, exist_ok=True)
    traces = []
    for n, mode in [(1000000, "repeat"), (100000, "unique")]:
        path = out / f"ev_{mode}.tsv"
        traces.append((path, n))
        if not path.exists():
            # An interrupted generation must not publish a shortened trace.
            part = path.with_suffix(".tsv.part")
            with part.open("w") as f:
                subprocess.run([sys.executable, "-I", str(here / "genevents.py"), str(n), mode], stdout=f, check=True)
            part.replace(path)
    exe = out / "route_aot"
    route = here / "route.py"
    rules = here / "rules.txt"
    t = time.perf_counter()
    subprocess.run([args.compiler, "build", str(route), "-o", str(exe)], check=True)
    build_seconds = time.perf_counter() - t
    print(f"pystachy build route.py: {build_seconds:.2f} s")
    records = []
    print(f"{'trace':7} {'mode':11} {'CPython':>8} {'AOT':>8} {'speedup':>7} {'routing: CPython':>17} {'AOT':>9} {'speedup':>7} {'RSS: CPython':>13} {'AOT':>8}")
    for trace, events in traces:
        for mode in ["", "--no-cache", "--fnmatch"]:
            extra = [mode] if mode else []
            commands = [[sys.executable, "-I", str(route), str(rules), str(trace)] + extra,
                        [str(exe), str(rules), str(trace)] + extra]
            samples = measure_pair(commands, args.runs, events)
            c, a = samples
            cw, aw = statistics.median(c["wall_s"]), statistics.median(a["wall_s"])
            cr, ar = statistics.median(c["routing_s"]), statistics.median(a["routing_s"])
            rc, ra = [peak_rss(cmd, expected=c["report"])[0] for cmd in commands]
            name = trace.stem[3:]
            print(f"{name:7} {mode or 'cached':11} {cw:7.3f}s {aw:7.3f}s {cw / aw:6.2f}x {cr * 1e9 / events:14.0f} ns {ar * 1e9 / events:6.0f} ns {cr / ar:6.2f}x {rc / 1024:10.1f} MiB {ra / 1024:5.1f} MiB")
            records.append({"trace": name, "events": events, "mode": mode or "cached", "commands": commands,
                            "samples": samples, "rss_kib": [rc, ra]})
    # --names adds a dict of distinct names, which grows on the all-new trace.
    names_rss = []
    for trace, events in traces:
        name = trace.stem[3:]
        rc, report = peak_rss([sys.executable, "-I", str(route), str(rules), str(trace), "--names"])
        if not report.startswith(f"{events} events, "):
            raise ValueError(f"event count differs in --names RSS run: {report!r}")
        ra, _ = peak_rss([str(exe), str(rules), str(trace), "--names"], expected=report)
        print(f"{name:7} cached, --names: RSS CPython {rc / 1024:.1f} MiB, AOT {ra / 1024:.1f} MiB")
        names_rss.append({"trace": name, "rss_kib": [rc, ra]})
    if args.json:
        result = {"provenance": provenance(root, args.compiler, [route, rules, here / "genevents.py", here / "bench.py", exe] + [t[0] for t in traces]),
                  "runs": args.runs, "build_s": build_seconds, "records": records, "names_rss": names_rss}
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
