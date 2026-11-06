"""Compare already-built commands; keep compilation out of runtime timings.

    python3 -I bench/gc_locality/run.py --config build/gc-config.json \
        --cpu 3 --rounds 5 --json build/gc-results.json

See README.md for the config format. No shell is used. Every occurrence of
{output} in an argument becomes a fresh temporary output path, hashed after the
run. Stdout and output files are streamed, so self-frontend IR stays off-heap.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

GC = re.compile(r"^gc: (\d+) collections, ([\d.]+) ms; heap peak ([\d.]+) MiB; live ([\d.]+) MiB at the last$")
GC_PHASES = re.compile(r"^gc phases: roots ([\d.]+) ms; trace ([\d.]+) ms; sweep ([\d.]+) ms$")
GC_WORK = re.compile(r"^gc work: root words (\d+); heap words (\d+); scanned objects (\d+); range pushes (\d+); chunk visits (\d+)$")
METRICS = ("wall_s", "user_s", "system_s", "peak_rss_kib", "minor_faults", "major_faults")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_info(cwd):
    def query(*args):
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None
    return {"revision": query("rev-parse", "HEAD"),
            "status": query("status", "--porcelain", "--untracked-files=all")}


def environment(extra):
    # Explicit config values override this sanitized environment. In particular,
    # inherited stress/GC/cache/optimization settings cannot pollute a comparison.
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("PYSTACHY_", "GC_")) and k not in ("LD_PRELOAD", "PYTHONPATH", "PYTHONHOME")}
    base.update(extra)
    return base


def describe(variant, common):
    cwd = str(Path(variant.get("cwd", common.get("cwd", "."))).resolve())
    env = dict(common.get("env", {}), **variant.get("env", {}))
    limit = None
    if "address_space_mib" in variant or "address_space_mib" in common:
        limit = variant.get("address_space_mib", common.get("address_space_mib"))
        if type(limit) is not int or limit <= 0:
            raise ValueError("address_space_mib must be a positive integer")
        hard = resource.getrlimit(resource.RLIMIT_AS)[1]
        if limit * 1048576 > sys.maxsize or (hard != resource.RLIM_INFINITY and limit * 1048576 > hard):
            raise ValueError("address_space_mib exceeds the inherited hard limit or platform range")
    exe = variant["argv"][0]
    # exec resolves relative PATH entries after chdir, not in the controller's cwd.
    search_path = os.pathsep.join(str(Path(cwd, entry)) for entry in os.get_exec_path(environment(env)))
    resolved = str(Path(cwd, exe)) if "/" in exe else shutil.which(exe, path=search_path)
    if resolved is None:
        raise FileNotFoundError(f"cannot resolve {exe!r} in variant {variant['name']!r}'s PATH")
    candidate = Path(resolved)
    actual_hash = digest(candidate)
    expected_hash = variant.get("validated_executable_sha256")
    if expected_hash is not None and actual_hash != expected_hash:
        raise ValueError(f"{variant['name']}: executable differs from validated build")
    files = {}
    for name in common.get("inputs", []) + variant.get("inputs", []):
        path = Path(cwd, name).resolve()
        files[str(path)] = digest(path)
    return dict(variant, cwd=cwd, env=env, address_space_mib=limit, inputs_sha256=files,
                executable_path=str(candidate.resolve()), executable_sha256=actual_hash,
                checkout=git_info(cwd))


def diagnostics(path):
    gc_lines, reports = [], []
    profile = {"phases": [], "work": []}
    with open(path, "rb") as err:
        for raw in err:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith(("gc:", "gc phases:", "gc work:")):
                gc_lines.append(line[:1024])
                gc_lines = gc_lines[-16:]
            m = GC.match(line)
            if m:
                reports.append(dict(collections=int(m[1]), elapsed_ms=float(m[2]),
                                    heap_peak_mib=float(m[3]), last_live_mib=float(m[4])))
            m = GC_PHASES.match(line)
            if m:
                profile["phases"].append(dict(roots_ms=float(m[1]), trace_ms=float(m[2]), sweep_ms=float(m[3])))
            m = GC_WORK.match(line)
            if m:
                profile["work"].append(dict(root_words=int(m[1]), heap_words=int(m[2]),
                                            scanned_objects=int(m[3]), range_pushes=int(m[4]), chunk_visits=int(m[5])))
        err.seek(max(0, err.tell() - 4096))
        tail = err.read().decode("utf-8", "replace")
    return gc_lines, reports, profile, tail


def measure(variant, cpu, phase, round_number):
    def prepare_child():
        os.sched_setaffinity(0, {cpu})
        if variant.get("address_space_mib") is not None:
            limit = variant["address_space_mib"] * 1048576
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    with tempfile.TemporaryDirectory(prefix="pystachy-gc-") as tmp:
        artifact = Path(tmp, "output")
        argv = [arg.replace("{output}", str(artifact)) for arg in variant["argv"]]
        out_path, err_path = Path(tmp, "stdout"), Path(tmp, "stderr")
        started = time.perf_counter()
        with open(out_path, "wb") as out, open(err_path, "wb") as err:
            p = subprocess.Popen(argv, cwd=variant["cwd"], env=environment(variant["env"]),
                                 stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 preexec_fn=prepare_child)
            try:
                _, status, usage = os.wait4(p.pid, 0)
            except BaseException:
                p.kill()
                p.wait()
                raise
            p.returncode = os.waitstatus_to_exitcode(status)
        wall = time.perf_counter() - started
        gc_lines, reports, profile, tail = diagnostics(err_path)
        has_artifact = any("{output}" in arg for arg in variant["argv"])
        return {"variant": variant["name"], "phase": phase, "round": round_number,
                "returncode": p.returncode, "wall_s": wall, "user_s": usage.ru_utime,
                "system_s": usage.ru_stime, "peak_rss_kib": usage.ru_maxrss,
                "minor_faults": usage.ru_minflt, "major_faults": usage.ru_majflt,
                "stdout_sha256": digest(out_path), "stdout_bytes": out_path.stat().st_size,
                "artifact_sha256": digest(artifact) if has_artifact and artifact.is_file() else None,
                "artifact_bytes": artifact.stat().st_size if has_artifact and artifact.is_file() else None,
                "gc_reports": reports, "gc_lines": gc_lines, "gc_profile": profile, "stderr_tail": tail}


def summary(samples, names):
    rows = {}
    for name in names:
        rs = [s for s in samples if s["variant"] == name and s["phase"] == "measure"]
        if not rs:
            continue
        row = {key: statistics.median(s[key] for s in rs) for key in METRICS}
        row["samples"] = len(rs)
        row["all_outputs_match"] = all(s["output_matches"] for s in rs)
        # Runtime gc_ns is elapsed collection time, not a measurement of GC CPU.
        for field in ("collections", "elapsed_ms", "heap_peak_mib", "last_live_mib"):
            if all(len(s["gc_reports"]) == 1 for s in rs):
                row["gc_" + field] = statistics.median(s["gc_reports"][0][field] for s in rs)
        rows[name] = row
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--cpu", required=True, type=int)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--warmups", type=int, default=1)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    if platform.system() != "Linux" or not hasattr(os, "wait4"):
        ap.error("Linux wait4 and CPU affinity are required (RSS is reported in KiB)")
    if a.rounds < 1 or a.warmups < 0:
        ap.error("rounds must be positive; warmups must be nonnegative")
    if a.cpu not in os.sched_getaffinity(0):
        ap.error("requested CPU is outside the current process affinity")
    config = json.loads(Path(a.config).read_text())
    variants = config.get("variants", [])
    if len(variants) < 2 or len({v["name"] for v in variants}) != len(variants):
        ap.error("provide at least two variants with distinct names")
    for v in variants:
        if not isinstance(v.get("argv"), list) or not v["argv"] or not all(isinstance(x, str) for x in v["argv"]):
            ap.error("each variant needs a nonempty argv list of strings")
    artifacts = [any("{output}" in arg for arg in v["argv"]) for v in variants]
    if any(artifacts) and not all(artifacts):
        ap.error("all variants must write {output} when any variant does")
    variants = [describe(v, config) for v in variants]
    cpu_model = next((s.partition(":")[2].strip() for s in Path("/proc/cpuinfo").read_text().splitlines()
                      if s.startswith("model name")), "unknown")
    report = {"schema_version": 1, "workload": config.get("name", Path(a.config).stem),
              "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "platform": platform.platform(), "python": sys.version, "cpu_model": cpu_model,
              "cpu": a.cpu, "allowed_cpus": sorted(os.sched_getaffinity(0)),
              "logical_cpus": os.cpu_count(), "loadavg_before": os.getloadavg(),
              "rounds": a.rounds, "warmups": a.warmups, "variants": variants,
              "notes": config.get("notes", ""), "samples": []}
    expected = None
    completed = False
    destination = Path(a.json)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        for phase, count in (("warmup", a.warmups), ("measure", a.rounds)):
            for rnd in range(count):
                order = variants[rnd % len(variants):] + variants[:rnd % len(variants)]
                for variant in order:
                    result = measure(variant, a.cpu, phase, rnd)
                    signature = (result["stdout_sha256"], result["artifact_sha256"])
                    valid = result["returncode"] == 0 and (not all(artifacts) or result["artifact_sha256"] is not None)
                    if valid and expected is None:
                        expected = signature
                    result["output_matches"] = valid and signature == expected
                    report["samples"].append(result)
                    print(f"{phase} {rnd + 1} {variant['name']}: {result['wall_s']:.4f}s, "
                          f"{result['peak_rss_kib'] / 1024:.1f} MiB, "
                          f"{'ok' if result['output_matches'] else 'FAILED'}", file=sys.stderr, flush=True)
                    if not result["output_matches"]:
                        raise RuntimeError(f"{variant['name']}: exit status, output, or artifact differs; see {a.json}")
        completed = True
    finally:
        report["complete"] = completed
        report["loadavg_after"] = os.getloadavg()
        report["summary"] = summary(report["samples"], [v["name"] for v in variants])
        report["all_outputs_match"] = bool(report["samples"]) and all(s["output_matches"] for s in report["samples"])
        destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
