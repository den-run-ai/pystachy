"""Uninstrumented native-driver JIT timings for the final PR 996 policy.

One CPython oracle, one cold-cache build and one warm-cache reuse per role,
then six balanced AB/BA pairs. All commands and observations are retained.
This controller does not change compiler sources, use LLVM wrappers, or profile.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import signal
import statistics
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parent.parent
LLVM = Path("/usr/lib/llvm-18/bin")
PYTHON = ROOT / "toolchain/python/cpython-3.13.16-linux-x86_64-gnu/bin/python3.13"
SOURCE = ROOT / "pystachy-baseline/bench/smoke/text.py"
HOMES = {
    "baseline": ROOT / "pystachy-policy-final/build/ref",
    "candidate": ROOT / "pystachy-policy-final",
}
REVISIONS = {
    "baseline": "ea68529b8a590eb8f3df7200b857e1d16becd7a3",
    "candidate": "44b638bbf8df1835b67bebda0468d65374569c71",
}
LLVM_TOOLS = ("clang", "opt", "lli", "llvm-as", "llvm-link", "llvm-dis")
ROLES = ("baseline", "candidate")
ORDERS = [ROLES if pair % 2 == 0 else tuple(reversed(ROLES)) for pair in range(6)]
MODE, N, CORE = "fnmatch", 1000, 0


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def identity(path, hashed=True):
    path = Path(path)
    before = path.stat()
    result = {
        "path": str(path), "realpath": str(path.resolve()),
        "bytes": before.st_size, "mode": before.st_mode,
        "mtime_ns": before.st_mtime_ns, "ctime_ns": before.st_ctime_ns,
        "inode": before.st_ino, "device": before.st_dev,
        "symlink": os.readlink(path) if path.is_symlink() else None,
    }
    if hashed:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino):
        raise RuntimeError("file changed while being identified: " + str(path))
    return result


def home_inputs(compiler_home):
    paths = [compiler_home / name for name in (
        "pystachy.py", "runtime.py", "runtime.c", "pyembed.c", "pyext.c",
        "VERSION", "REVISION", "commit") if (compiler_home / name).is_file()]
    for directory in ("src", "lib", "ryu", "mpz"):
        paths.extend(path for path in (compiler_home / directory).rglob("*")
                     if path.is_file() and path.suffix in (".py", ".c", ".h"))
    return {str(path.relative_to(compiler_home)): identity(path)
            for path in sorted(set(paths))}


def cache_snapshot(directory, hashed=True):
    return {str(path.relative_to(directory)): identity(path, hashed)
            for path in sorted(directory.rglob("*")) if path.is_file()}


def runtime_artifacts(snapshot):
    return {name: value for name, value in snapshot.items()
            if name.endswith((".bc", ".o", ".so", ".target"))}


def without_hashes(snapshot):
    return {name: {key: value for key, value in info.items() if key != "sha256"}
            for name, info in snapshot.items()}


def environment(directory, role=None):
    # An explicit environment avoids inherited profiling/optimization switches.
    # HOME is retained unchanged; no credentials or unrelated environment values
    # are copied into children or evidence.
    env = {
        "PATH": str(LLVM) + ":/usr/bin:/bin", "LC_ALL": "C", "LANG": "C",
        "TZ": "UTC", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1",
        "TMPDIR": str(directory / "tmp" / (role or "metadata")),
    }
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    if role is not None:
        env.update(PYSTACHY_HOME=str(HOMES[role]), PYSTACHY_LLVM=str(LLVM),
                   PYSTACHY_CACHE=str(directory / role / "cache"), PYSTACHY_OPT="")
    return env


def context():
    result = {"utc": utc(), "affinity": sorted(os.sched_getaffinity(0)),
              "load_average": list(os.getloadavg())}
    paths = ["/proc/loadavg", "/proc/stat", "/proc/meminfo",
             "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
             "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"]
    for name in paths:
        try:
            result[name] = Path(name).read_text()
        except OSError as error:
            result[name] = {"unavailable": str(error)}
    return result


def execute(command, cwd, env, prefix, timeout):
    """Run the command directly; child CPU includes its reaped descendants."""
    command = [str(part) for part in command]
    prefix.parent.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = Path(str(prefix) + ".stdout"), Path(str(prefix) + ".stderr")
    record_path = Path(str(prefix) + ".json")
    record = {"command": command, "cwd": str(cwd), "environment": env,
              "timeout_s": timeout, "start_context": context(),
              "stdout_file": str(stdout_path), "stderr_file": str(stderr_path),
              "returncode": None, "timed_out": False, "complete": False}
    save(record_path, record)
    child = None
    interrupted = None
    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            child = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                     start_new_session=True)
            record["pid"] = child.pid
            def alarm_handler(signum, frame):
                raise subprocess.TimeoutExpired(command, timeout)
            previous_handler = signal.signal(signal.SIGALRM, alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout)
            try:
                # A blocking waitpid avoids Popen.wait(timeout)'s polling delay,
                # which can otherwise add tens of milliseconds to short samples.
                record["returncode"] = child.wait()
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                record["returncode"] = child.returncode
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
            record["complete"] = True
    except BaseException as error:
        record["exception"] = repr(error)
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            record["returncode"] = child.returncode
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            interrupted = error
    finally:
        wall_ns = time.perf_counter_ns() - start
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record.update(wall_ns=wall_ns, wall_s=wall_ns / 1e9,
                      cpu_user_s=cpu_after.ru_utime - cpu_before.ru_utime,
                      cpu_system_s=cpu_after.ru_stime - cpu_before.ru_stime,
                      voluntary_context_switches=cpu_after.ru_nvcsw - cpu_before.ru_nvcsw,
                      involuntary_context_switches=cpu_after.ru_nivcsw - cpu_before.ru_nivcsw,
                      end_context=context())
        record["cpu_s"] = record["cpu_user_s"] + record["cpu_system_s"]
        for name, path in (("stdout", stdout_path), ("stderr", stderr_path)):
            if path.exists():
                record[name] = path.read_bytes().decode("utf-8", errors="backslashreplace")
                record[name + "_identity"] = identity(path)
        save(record_path, record)
    if interrupted is not None:
        raise interrupted
    return record


def parse_loop(stderr):
    matches = re.findall(r"^seconds ([^\r\n]+)\r?$", stderr, re.M)
    if len(matches) != 1:
        raise ValueError("expected exactly one in-program seconds line")
    value = float(matches[0])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("in-program seconds must be finite and positive")
    return value


def output_valid(record, expected):
    issues = []
    if not record.get("complete") or record.get("returncode") != 0 or record.get("timed_out"):
        issues.append("command did not complete successfully")
    if record.get("stdout") != expected:
        issues.append("stdout differs from the CPython oracle")
    try:
        record["loop_s"] = parse_loop(record.get("stderr", ""))
    except ValueError as error:
        issues.append(str(error))
    record["validation_errors"] = issues
    record["valid"] = not issues
    return not issues


def snapshot_inputs(dependencies):
    return {
        "controller": identity(Path(__file__)), "source": identity(SOURCE),
        "binaries": {role: identity(HOMES[role] / "pystachy") for role in ROLES},
        "homes": {role: home_inputs(HOMES[role]) for role in ROLES},
        "tools": {name: identity(LLVM / name) for name in LLVM_TOOLS},
        "python": identity(PYTHON), "shell": identity(Path("/bin/sh")),
        "dynamic_dependencies": {path: identity(Path(path)) for path in sorted(dependencies)},
    }


def metadata(directory, env):
    records = {}
    dependencies = set()
    for name, path in [(name, LLVM / name) for name in LLVM_TOOLS] + [("python", PYTHON)]:
        record = execute([path, "--version"], ROOT, env, directory / (name + "-version"), 30)
        records[name + "_version"] = record
        wanted = "Python 3.13.16" if name == "python" else None
        text = record.get("stdout", "") + record.get("stderr", "")
        if record["returncode"] != 0 or (wanted is not None and wanted not in text):
            raise RuntimeError("unexpected version invocation: " + name)
        if name != "python" and not re.search(r"\bversion\s+18\.", text, re.I):
            raise RuntimeError("LLVM 18 required for " + name)
    paths = {name: LLVM / name for name in LLVM_TOOLS}
    paths.update({role + "-compiler": HOMES[role] / "pystachy" for role in ROLES})
    paths.update(python=PYTHON, shell=Path("/bin/sh"))
    for name, path in paths.items():
        record = execute(["/usr/bin/ldd", path], ROOT, env, directory / (name + "-ldd"), 30)
        records[name + "_ldd"] = record
        if record["returncode"] != 0:
            raise RuntimeError("could not record dependencies for " + name)
        for match in re.findall(r"(/[^\s()]+)", record.get("stdout", "")):
            if Path(match).is_file():
                dependencies.add(match)
    return records, dependencies


def summary(observations):
    if len(observations) != 12 or any(not item.get("valid") for item in observations):
        raise ValueError("all twelve measured samples must be valid; none can be discarded")
    by_pair = {}
    for item in observations:
        pair = by_pair.setdefault(item["pair"], {})
        if item["role"] in pair:
            raise ValueError("duplicate role in a pair")
        pair[item["role"]] = item
    if set(by_pair) != set(range(1, 7)) or any(set(pair) != set(ROLES) for pair in by_pair.values()):
        raise ValueError("expected six complete baseline/candidate pairs")
    result = {}
    for metric in ("wall_s", "cpu_s", "loop_s"):
        values = {role: [by_pair[pair][role][metric] for pair in range(1, 7)] for role in ROLES}
        if any(not math.isfinite(value) or value <= 0 for samples in values.values() for value in samples):
            raise ValueError("timings must all be finite and positive")
        medians = {role: statistics.median(samples) for role, samples in values.items()}
        changes = [(values["candidate"][pair] / values["baseline"][pair] - 1) * 100 for pair in range(6)]
        result[metric] = {
            "all_six_samples": values, "medians": medians,
            "candidate_vs_baseline_median_pct": (medians["candidate"] / medians["baseline"] - 1) * 100,
            "all_six_paired_candidate_changes_pct": changes,
            "median_paired_candidate_change_pct": statistics.median(changes),
            "candidate_slower_pairs": sum(change > 0 for change in changes),
            "equal_pairs": sum(change == 0 for change in changes),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "jit-native-time",
                        help="fresh evidence directory; an existing directory is rejected")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per workload invocation")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report_path = directory / "report.json"
    report = {
        "schema": 1, "controller_command": sys.argv, "started_utc": utc(),
        "controller_python": sys.version, "platform": platform.platform(),
        "source_path": str(SOURCE), "mode": MODE, "n": N,
        "requested_core": CORE, "original_affinity": sorted(os.sched_getaffinity(0)),
        "expected_revisions": REVISIONS, "homes": {role: str(HOMES[role]) for role in ROLES},
        "pair_orders": ORDERS, "warm_phases": [], "observations": [], "errors": [],
        "complete": False, "valid": False, "performance_hold_retained": True,
        "scope": "Whole native-driver JIT process, including frontend, LLVM optimization, JIT code generation, program execution, runtime and GC. In-program loop timing is reported separately.",
        "method": "Direct native commands, inherited core-0 affinity, real LLVM 18, separate homes and fresh caches. No wrappers, profiling, per-sample threshold, sample discard or retries.",
        "cpu_accounting": "RUSAGE_CHILDREN user+system deltas around a serial direct child, including descendants waited by that child.",
        "cache_evidence": "Artifact identities and metadata before/after warm reuse and measurement; no instrumented tool-call or loaded-object trace is collected.",
        "interpretation": "No performance acceptance threshold is applied. Timing variability and all samples remain visible; instruction improvements do not establish a wall-time win.",
    }
    save(report_path, report)
    dependencies = set()
    measured_before = None
    cache_ready = {}
    try:
        if CORE not in os.sched_getaffinity(0):
            raise RuntimeError("requested CPU 0 is not available; no substitute core will be used")
        os.sched_setaffinity(0, {CORE})
        report["effective_affinity"] = sorted(os.sched_getaffinity(0))
        report["system_before"] = context()
        report["cpuinfo"] = Path("/proc/cpuinfo").read_text()
        for path in [PYTHON, *[LLVM / name for name in LLVM_TOOLS],
                     *[HOMES[role] / "pystachy" for role in ROLES]]:
            with path.open("rb") as stream:
                if stream.read(4) != b"\x7fELF" or not os.access(path, os.X_OK):
                    raise RuntimeError("expected a native ELF executable: " + str(path))
        if (HOMES["baseline"] / "commit").read_text().strip() != REVISIONS["baseline"]:
            raise RuntimeError("reference commit marker differs from pinned baseline")
        env = environment(directory)
        revision = execute(["/usr/bin/git", "rev-parse", "HEAD"], HOMES["candidate"], env,
                           directory / "metadata/candidate-revision", 30)
        report["candidate_revision"] = revision
        if revision["returncode"] != 0 or revision.get("stdout", "").strip() != REVISIONS["candidate"]:
            raise RuntimeError("candidate checkout differs from pinned final revision")
        report["metadata"], dependencies = metadata(directory / "metadata", env)
        report["inputs_before"] = snapshot_inputs(dependencies)
        role_envs = {role: environment(directory, role) for role in ROLES}
        for role in ROLES:
            (directory / role / "cache").mkdir(parents=True, exist_ok=False)
        report["cache_before"] = {role: cache_snapshot(directory / role / "cache") for role in ROLES}
        save(report_path, report)
        oracle = execute([PYTHON, SOURCE, MODE, N], SOURCE.parent, env, directory / "cpython", args.timeout)
        report["cpython"] = oracle
        expected = str(6 * N) + "\n"
        if not output_valid(oracle, expected):
            raise RuntimeError("pinned CPython oracle did not pass")
        save(report_path, report)
        for phase in ("warm-build", "warm-reuse"):
            for role in ROLES:
                print(phase, role, flush=True)
                record = execute([HOMES[role] / "pystachy", "run", SOURCE, MODE, N],
                                 HOMES[role], role_envs[role], directory / role / phase / "driver", args.timeout)
                output_valid(record, oracle["stdout"])
                record.update(role=role, phase=phase)
                record["cache_after"] = cache_snapshot(directory / role / "cache")
                artifacts = runtime_artifacts(record["cache_after"])
                suffixes = {Path(name).suffix for name in artifacts}
                if not {".bc", ".o", ".so", ".target"}.issubset(suffixes):
                    record["valid"] = False
                    record["validation_errors"].append("prepared runtime artifact set is incomplete")
                if phase == "warm-build":
                    cache_ready[role] = artifacts
                elif cache_ready[role] != artifacts:
                    record["valid"] = False
                    record["validation_errors"].append("runtime artifacts changed during warm reuse")
                report["warm_phases"].append(record)
                save(report_path, report)
        if any(not record["valid"] for record in report["warm_phases"]):
            raise RuntimeError("warm preparation/reuse failed; no timed samples were attempted")
        measured_before = snapshot_inputs(dependencies)
        report["inputs_before_measurement"] = measured_before
        report["inputs_stable_through_preparation"] = report["inputs_before"] == measured_before
        report["cache_before_measurement"] = {role: cache_snapshot(directory / role / "cache") for role in ROLES}
        save(report_path, report)
        for pair, order in enumerate(ORDERS, 1):
            for position, role in enumerate(order, 1):
                print("pair", pair, "position", position, role, flush=True)
                cache = directory / role / "cache"
                cache_before = runtime_artifacts(cache_snapshot(cache, hashed=False))
                record = execute([HOMES[role] / "pystachy", "run", SOURCE, MODE, N],
                                 HOMES[role], role_envs[role],
                                 directory / "samples" / f"pair-{pair}-{position}-{role}" / "driver", args.timeout)
                output_valid(record, oracle["stdout"])
                record.update(role=role, pair=pair, position=position, phase="measured")
                record["cache_stat_before"] = cache_before
                record["cache_stat_after"] = runtime_artifacts(cache_snapshot(cache, hashed=False))
                record["warm_artifacts_unchanged"] = (
                    cache_before == without_hashes(cache_ready[role]) == record["cache_stat_after"])
                if not record["warm_artifacts_unchanged"]:
                    record["valid"] = False
                    record["validation_errors"].append("prepared runtime artifact metadata changed")
                report["observations"].append(record)
                save(report_path, report)
        report["complete"] = len(report["observations"]) == 12
    except BaseException as error:
        report["errors"].append(repr(error))
        report["exception_traceback"] = traceback.format_exc()
    finally:
        try:
            report["inputs_after"] = snapshot_inputs(dependencies)
            report["inputs_stable"] = report.get("inputs_before") == report["inputs_after"]
            report["measurement_inputs_stable"] = measured_before == report["inputs_after"]
            report["cache_after"] = {role: cache_snapshot(directory / role / "cache") for role in ROLES}
            report["runtime_artifacts_stable"] = bool(cache_ready) and all(
                role in cache_ready and cache_ready[role] == runtime_artifacts(report["cache_after"][role])
                for role in ROLES)
            report["system_after"] = context()
        except BaseException as error:
            report["errors"].append("final identity capture: " + repr(error))
        valid_samples = len(report["observations"]) == 12 and all(row["valid"] for row in report["observations"])
        if valid_samples:
            try:
                report["statistics"] = summary(report["observations"])
            except ValueError as error:
                report["errors"].append("statistics: " + str(error))
        report["valid"] = bool(
            report["complete"] and valid_samples and not report["errors"]
            and report.get("inputs_stable") and report.get("measurement_inputs_stable")
            and report.get("runtime_artifacts_stable")
            and all(row["valid"] for row in report["warm_phases"]))
        report["finished_utc"] = utc()
        save(report_path, report)
    print(json.dumps({"report": str(report_path), "complete": report["complete"],
                      "valid": report["valid"], "errors": report["errors"],
                      "statistics": report.get("statistics")}, indent=2), flush=True)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
