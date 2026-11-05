r"""Interleave opt-in compiler jobs and full-LTO partitions against serial AOT.

Linux research controller, run on CPython. Nothing here changes production defaults.
For example (a native compiler must already have been built):

  python3 bench/compiler_parallel/llvm_partitions.py --compiler ./pystachy \
      --workload tiny --workload json-repair --jobs 4 --samples 3 \
      --json /tmp/compiler-parallel.json

Add --workload self for compiler self-builds. An external, CPython-compatible
probe can be supplied as --workload namegen=/path/probe.py, with repeatable
--import-path namegen=/path/modules and --arg namegen=ARG. Source directories
are inventoried; the controller never fetches or silently modifies a workload.

Build wall time includes compiler startup, cache lookup, frontend, LLVM and link.
Cold means a fresh runtime cache, not a cold OS page cache. Warm uses a successful
untimed serial prewarm. Process-tree RSS is a sampled sum (shared pages counted
per process, short peaks can be missed); wait4's maximum is reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_INTERVAL = 0.01
WAIT_INTERVAL = 0.001
NAMEGEN_PROBE = ROOT / "bench/compiler_parallel/namegen_probe.py"
NAMEGEN_URL = "https://raw.githubusercontent.com/python/mypy/1231cf158a9cab0c41f613f3d8070c1332632f29/mypyc/namegen.py"
NAMEGEN_SHA256 = "739a7bcb1c54c96a8944da8a9a4542475c56d2ee392db22ba933e74749fe23ae"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def proc_child_pid(pid: int) -> int | None:
    # Some sandboxes enter a PID namespace without remounting /proc. In that
    # case /proc/<Popen.pid> can name an unrelated process in the outer namespace.
    # Resolve only our direct children, matching the innermost NSpid component.
    try:
        status = Path("/proc/self/status").read_text().splitlines()
        outer = next(int(line.split()[1]) for line in status if line.startswith("Pid:"))
        if outer == os.getpid():
            return pid
        matches = []
        for child, parent, _ in proc_snapshot():
            if parent != outer:
                continue
            try:
                lines = (Path("/proc") / str(child) / "status").read_text().splitlines()
                ids = next(line.split()[1:] for line in lines if line.startswith("NSpid:"))
                if int(ids[-1]) == pid:
                    matches.append(child)
            except (OSError, ValueError, StopIteration):
                pass
        if len(matches) == 1:
            return matches[0]
    except (OSError, ValueError, StopIteration):
        pass
    return None


def proc_snapshot() -> list[tuple[int, int, int]]:
    # /proc/PID/task/TID/children is optional (CONFIG_CHECKPOINT_RESTORE).
    # stat is the portable Linux alternative: read parent and resident pages.
    rows = []
    page_kib = os.sysconf("SC_PAGE_SIZE") // 1024
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            stat = (directory / "stat").read_text()
            fields = stat[stat.rfind(")") + 2:].split()
            rows.append((int(directory.name), int(fields[1]), int(fields[21]) * page_kib))
        except (OSError, ValueError, IndexError):
            pass
    return rows


def process_tree_rss(pid: int) -> tuple[int, int]:
    """Sample living descendants, including children launched by worker threads."""
    children, resident = {}, {}
    for child, parent, size in proc_snapshot():
        children.setdefault(parent, []).append(child)
        resident[child] = size
    pending, seen, rss = [pid], set(), 0
    while pending:
        child = pending.pop()
        if child in seen or child not in resident:
            continue
        seen.add(child)
        rss += resident[child]
        pending.extend(children.get(child, []))
    return rss, len(seen)


def execute(command: list[str], env: dict[str, str], timeout: float,
            stdin: Path | None = None) -> dict:
    """Measure one isolated process tree; stdout/stderr cannot fill a pipe."""
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        incoming = stdin.open("rb") if stdin else open(os.devnull, "rb")
        try:
            start = time.monotonic()
            load = os.getloadavg()
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=incoming,
                                       stdout=output, stderr=errors, start_new_session=True)
            proc_pid = proc_child_pid(process.pid)
            peak, processes, timed_out, sampled = 0, 0, False, 0.0
            try:
                while True:
                    now = time.monotonic()
                    if proc_pid is not None and now - sampled >= SAMPLE_INTERVAL:
                        rss, count = process_tree_rss(proc_pid)
                        peak, processes = max(peak, rss), max(processes, count)
                        sampled = now
                    waited, status, usage = os.wait4(process.pid, os.WNOHANG)
                    if waited:
                        process.returncode = os.waitstatus_to_exitcode(status)
                        break
                    if time.monotonic() - start > timeout:
                        timed_out = True
                        os.killpg(process.pid, signal.SIGKILL)
                        _, status, usage = os.wait4(process.pid, 0)
                        process.returncode = os.waitstatus_to_exitcode(status)
                        break
                    time.sleep(WAIT_INTERVAL)
            except BaseException:
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    _, status, _ = os.wait4(process.pid, 0)
                    process.returncode = os.waitstatus_to_exitcode(status)
                raise
            wall = time.monotonic() - start
        finally:
            incoming.close()
        output.seek(0)
        errors.seek(0)
        stdout, stderr = output.read(), errors.read()
    return {
        "command": command, "exit_code": process.returncode, "timed_out": timed_out,
        "wall_s": wall, "cpu_s": usage.ru_utime + usage.ru_stime,
        "sampled_process_tree_peak_rss_kib": peak if peak > 0 else None,
        "wait4_max_process_rss_kib": usage.ru_maxrss,
        "sampled_max_processes": processes, "load_before": list(load),
        "proc_pid_resolved": proc_pid is not None,
        "load_after": list(os.getloadavg()), "stdout_sha256": digest(stdout),
        "stderr_sha256": digest(stderr),
        "stdout": stdout.decode("utf-8", "backslashreplace"),
        "stderr": stderr.decode("utf-8", "backslashreplace"),
    }


def successful(result: dict) -> None:
    if result["timed_out"] or result["exit_code"] != 0:
        raise RuntimeError(f"command failed: {shlex.join(result['command'])}\n"
                           f"exit={result['exit_code']} timeout={result['timed_out']}\n"
                           f"{result['stderr'][-3000:]}")


def build_stages(result: dict, variant: dict, state: str) -> list[dict]:
    if (result.get("proc_pid_resolved") is False
            or ("sampled_process_tree_peak_rss_kib" in result and result["sampled_process_tree_peak_rss_kib"] is None)):
        raise RuntimeError("aggregate build RSS unavailable: cannot resolve/sample the child in /proc's PID namespace")
    stages = []
    for line in result["stderr"].splitlines():
        if line.startswith("pystachy-timing\t"):
            _, name, seconds = line.split("\t")
            duration = float(seconds)
            if not 0 <= duration < float("inf"):
                raise RuntimeError("invalid compiler stage duration")
            stages.append({"stage": name, "seconds": duration})
    names = [stage["stage"] for stage in stages]
    if names.count("driver.total") != 1:
        raise RuntimeError("build did not emit one driver.total timing; rebuild this prototype's compiler")
    if ("program.lto_codegen_link" in names) != bool(variant["partitions"]):
        raise RuntimeError("build did not execute the requested LLVM backend")
    if state == "warm" and any(name in names for name in ("runtime.c", "runtime.parallel", "runtime.frontend")):
        raise RuntimeError("warm build unexpectedly rebuilt the runtime")
    if state == "cold" and (("runtime.parallel" in names) != (variant["jobs"] > 1)):
        raise RuntimeError("cold build did not execute the requested runtime scheduling path")
    return stages


def witness(result: dict, strip_seconds: bool) -> tuple:
    stdout = result["stdout_sha256"]
    if strip_seconds:
        # Only the existing JSON-repair workload's explicit timing lines vary.
        # Keep every result, checksum, record count and diagnostic in the oracle.
        lines, timers = [], []
        for line in result["stdout"].splitlines(keepends=True):
            if line.startswith(("seconds ", "warmup_seconds ")):
                value = float(line.split()[1])
                if not 0 <= value < float("inf"):
                    raise RuntimeError("invalid workload timer")
                timers.append(line.split()[0])
            else:
                lines.append(line)
        if timers != ["seconds"]:
            raise RuntimeError("missing or extra JSON-repair timing line")
        stdout = digest("".join(lines).encode("utf-8"))
    return result["exit_code"], stdout, result["stderr_sha256"]


def identify_sources(workloads: list[dict], extra_files: tuple[Path, ...] = ()) -> dict:
    files = {Path(__file__).resolve(), ROOT / "pystachy.py", ROOT / "runtime.c", ROOT / "runtime.py"}
    files.update(extra_files)
    directories = {ROOT / name for name in ("src", "lib", "ryu", "mpz")}
    for workload in workloads:
        files.add(workload["source"])
        directories.add(workload["source"].parent)
        directories.update(workload["imports"])
        if workload["stdin"]:
            files.add(workload["stdin"])
    for directory in directories:
        # Include untracked/ignored importable files and shadowing modules too.
        for suffix in ("*.py", "*.c", "*.h"):
            files.update(p for p in directory.rglob(suffix) if p.is_file())
    hashes = {str(p): file_digest(p) for p in sorted(files)}
    serialized = json.dumps(hashes, sort_keys=True).encode()
    return {"sha256": digest(serialized), "files": hashes}


def source_provenance(workloads: list[dict]) -> list[dict]:
    sources = []
    for workload in workloads:
        if workload["source"] != NAMEGEN_PROBE:
            continue
        imported = None
        for directory in [workload["source"].parent, *workload["imports"], ROOT / "lib"]:
            if (directory / "namegen/__init__.py").is_file():
                raise ValueError(f"a package shadows the pinned namegen module: {directory}")
            candidate = directory / "namegen.py"
            if candidate.is_file():
                imported = candidate
                break
        if imported is None or file_digest(imported) != NAMEGEN_SHA256:
            raise ValueError("namegen_probe.py requires the unchanged pinned namegen.py; use --import-path")
        sources.append({"workload": workload["name"], "path": str(imported),
                        "url": NAMEGEN_URL, "sha256": NAMEGEN_SHA256,
                        "adaptations": "none; the benchmark consumer is original"})
    return sources


def command_identity(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if not executable:
        raise ValueError(f"command not found: {command[0]}")
    files = {Path(executable).resolve()}
    files.update(Path(arg).resolve() for arg in command[1:] if Path(arg).is_file())
    return {str(path): file_digest(path) for path in sorted(files)}


def resolve_command(command: str) -> list[str]:
    parts = shlex.split(command)
    if not parts or not shutil.which(parts[0]):
        raise ValueError(f"command not found: {command}")
    resolved = [str(Path(shutil.which(parts[0])).resolve())]
    for index, arg in enumerate(parts[1:], 1):
        is_path = parts[index - 1] != "-m" and ("/" in arg or arg.endswith(".py")) and Path(arg).is_file()
        resolved.append(str(Path(arg).resolve()) if is_path else arg)
    return resolved


def write_report(path: Path | None, report: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False,
                                         prefix=path.name + ".", suffix=".tmp") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        os.replace(stream.name, path)


def assign_options(items: list[str], workloads: list[dict], field: str, paths: bool = False) -> None:
    by_name = {w["name"]: w for w in workloads}
    replaced = set()
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or name not in by_name:
            raise ValueError(f"expected a selected WORKLOAD=VALUE, got {item!r}")
        value = Path(value).resolve() if paths else value
        if field == "stdin":
            by_name[name][field] = value
        else:
            if field == "args" and name not in replaced:
                by_name[name][field] = []
                replaced.add(name)
            by_name[name][field].append(value)


def choose_workloads(specs: list[str], work: Path) -> list[dict]:
    tiny = work / "tiny.py"
    tiny.write_text('print("tiny", sum([1, 2, 3, 4]))\n')
    definitions = {
        "tiny": (tiny, [], []),
        "json-repair": (ROOT / "bench/json_repair/bench.py", ["500"], [ROOT / "ports/json_repair"]),
        "self": (ROOT / "pystachy.py", [], []),
    }
    workloads = []
    for spec in specs:
        if spec in definitions:
            source, args, imports = definitions[spec]
            name = spec
        else:
            name, separator, filename = spec.partition("=")
            if not separator or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ValueError(f"expected tiny, json-repair, self or NAME=PATH, got {spec!r}")
            if name in definitions:
                raise ValueError(f"reserved workload name: {name}")
            source, args, imports = Path(filename).resolve(), [], []
        if not source.is_file():
            raise ValueError(f"missing workload: {source}")
        if any(w["name"] == name for w in workloads):
            raise ValueError(f"duplicate workload: {name}")
        workloads.append({"name": name, "source": source, "args": list(args),
                          "imports": list(imports), "stdin": None})
    return workloads


def runtime_environment(base: dict[str, str], workload: dict) -> dict[str, str]:
    env = dict(base, PYSTACHY_HOME=str(ROOT))
    imports = os.pathsep.join(str(p) for p in workload["imports"])
    env["PYSTACHY_PATH"] = imports
    env["PYTHONPATH"] = imports
    return env


def validate_application(command: list[str], workload: dict, env: dict[str, str],
                         work: Path, timeout: float) -> tuple[list[dict], tuple]:
    if workload["name"] == "self":
        records, hashes = [], []
        for mode, source in (("ir", ROOT / "pystachy.py"), ("rt", ROOT / "runtime.py")):
            output = work / (mode + ".ll")
            output.unlink(missing_ok=True)
            result = execute(command + [mode, str(source), "-o", str(output)], env, timeout)
            successful(result)
            result["emitted_ir_sha256"] = file_digest(output)
            result["emitted_ir_bytes"] = output.stat().st_size
            records.append(result)
            hashes.append((result["emitted_ir_sha256"], witness(result, False)))
        return records, tuple(hashes)
    result = execute(command + workload["args"], env, timeout, workload["stdin"])
    successful(result)
    return [result], witness(result, workload["name"] == "json-repair")


def summarize(records: list[dict]) -> list[dict]:
    summaries = []
    keys = sorted({(r["workload"], r["cache"], r["variant"]) for r in records})
    for name, cache, variant in keys:
        rows = [r for r in records if (r["workload"], r["cache"], r["variant"]) == (name, cache, variant)]
        good = [r for r in rows if r.get("correct")]
        row = {"workload": name, "cache": cache, "variant": variant, "samples": len(good)}
        for metric in ("wall_s", "cpu_s", "sampled_process_tree_peak_rss_kib", "wait4_max_process_rss_kib"):
            values = [r["build"][metric] for r in good if r["build"][metric] is not None]
            row["build_median_" + metric] = statistics.median(values) if values else None
        row["binary_bytes"] = [r["binary_bytes"] for r in good]
        row["application_median_wall_s"] = statistics.median(
            sum(p["wall_s"] for p in run) for r in good for run in r["application"]
        ) if good else None
        stage_names = sorted({s["stage"] for r in good for s in r["build"]["stages"]})
        row["median_stage_s"] = {
            name: statistics.median(sum(s["seconds"] for s in r["build"]["stages"] if s["stage"] == name)
                                    for r in good) for name in stage_names
        }
        summaries.append(row)
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="native compiler command (shell-quoted arguments)")
    parser.add_argument("--python", default=sys.executable, help="CPython oracle command; use the repository's pinned version")
    parser.add_argument("--workload", action="append", help="tiny, json-repair, self or NAME=PATH; repeatable")
    parser.add_argument("--arg", action="append", default=[], help="WORKLOAD=ARG; replaces defaults, repeatable")
    parser.add_argument("--import-path", action="append", default=[], help="WORKLOAD=DIR; repeatable")
    parser.add_argument("--stdin", action="append", default=[], help="WORKLOAD=FILE")
    parser.add_argument("--jobs", type=int, default=4, help="one total per-build budget, 1..64")
    parser.add_argument("--no-overlap", action="store_true", help="omit the overlap-only control (useful for warm self-builds)")
    parser.add_argument("--partitions", help="comma-separated LTO counts; default: 1,2,4 within --jobs")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--runtime-samples", type=int, default=3)
    parser.add_argument("--cache", choices=("both", "cold", "warm"), default="both")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per build/application invocation")
    parser.add_argument("--llvm", type=Path, help="matching clang/LLVM/LLD directory")
    parser.add_argument("--json", type=Path, help="checkpoint raw samples and identities here")
    args = parser.parse_args()
    if sys.platform != "linux" or not hasattr(os, "wait4"):
        parser.error("this full-LTO and /proc measurement prototype requires Linux")
    if not 1 <= args.jobs <= 64 or min(args.samples, args.runtime_samples, args.timeout) <= 0:
        parser.error("jobs must be 1..64; samples, runtime-samples and timeout must be positive")
    partitions = ([int(n) for n in args.partitions.split(",")] if args.partitions
                  else [n for n in (1, 2, 4) if n <= args.jobs])
    if not partitions or len(set(partitions)) != len(partitions) or any(not 1 <= n <= args.jobs for n in partitions):
        parser.error("partitions must be unique positive counts within --jobs")
    compiler, python = resolve_command(args.compiler), resolve_command(args.python)
    variants = [{"name": "serial", "jobs": 1, "partitions": 0}]
    if args.jobs > 1 and not args.no_overlap:
        variants.append({"name": "overlap", "jobs": args.jobs, "partitions": 0})
    variants += [{"name": f"lto-{n}", "jobs": args.jobs, "partitions": n} for n in partitions]
    base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")
            and k not in ("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD")}
    llvm = args.llvm or Path(os.getenv("PYSTACHY_LLVM", "/usr/lib/llvm-18/bin"))
    base["PYSTACHY_LLVM"] = str(llvm.resolve())
    tools = {}
    for name in ("clang", "opt", "llvm-link", "llvm-as", "ld.lld"):
        path = llvm / name
        if not path.is_file():
            parser.error(f"missing matching tool: {path}; use --llvm")
        version = subprocess.check_output([str(path), "--version"], text=True).strip()
        tools[name] = {"path": str(path.resolve()), "sha256": file_digest(path), "version": version}
    report = {
        "status": "running", "schema": 1, "variants": variants,
        "platform": platform.platform(), "machine": platform.machine(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "llvm": tools,
        "compiler": command_identity(compiler), "python": command_identity(python),
        "python_version": subprocess.check_output(python + ["--version"], text=True).strip(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True),
        "sampling_interval_s": SAMPLE_INTERVAL,
        "wait_poll_interval_s": WAIT_INTERVAL,
        "requested_samples": args.samples, "runtime_samples": args.runtime_samples,
        "timeout_s": args.timeout,
        "memory_method": "10ms sampled sum of living descendant RSS; shared pages counted per process, short peaks may be missed. wait4 maximum is one process, not aggregate.",
        "cpu_method": "wait4 user+system CPU for compiler and descendants it waited for",
        "cache_method": "fresh runtime directory per cold build; untimed serial build prewarms a shared cache per workload; OS page cache is not flushed",
        "timing_method": "wall time includes startup and <=1ms wait polling; sub-millisecond runtime differences are inconclusive; nested/overlapping stage times must not be summed",
        "environment": {k: base[k] for k in ("PYSTACHY_LLVM", "PATH", "LD_LIBRARY_PATH", "LANG",
                                             "LC_ALL", "PYTHONHASHSEED", "OMP_NUM_THREADS") if k in base},
        "oracles": {}, "prewarm": [], "results": [],
    }
    for name in ("cpu.max", "memory.max", "cpuset.cpus.effective"):
        path = Path("/sys/fs/cgroup") / name
        if path.exists():
            report[name] = path.read_text().strip()
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            report["cpu_model"] = line.split(":", 1)[1].strip()
            break
    with tempfile.TemporaryDirectory(prefix="pystachy-compiler-parallel-") as temporary:
        work = Path(temporary)
        workloads = choose_workloads(args.workload or ["tiny", "json-repair"], work)
        assign_options(args.arg, workloads, "args")
        assign_options(args.import_path, workloads, "imports", paths=True)
        assign_options(args.stdin, workloads, "stdin", paths=True)
        report["third_party_sources"] = source_provenance(workloads)
        report["workloads"] = [{k: str(v) if isinstance(v, Path) else [str(p) for p in v] if k == "imports" else v
                                for k, v in w.items()} for w in workloads]
        # The runtime key is program-independent. Warming it with the tiny
        # generated control avoids compiling a large application (or the entire
        # compiler) just to populate the same runtime artifact.
        prewarm_source = work / "tiny.py"
        report["prewarm_input"] = {"path": str(prewarm_source), "sha256": file_digest(prewarm_source),
                                   "source": prewarm_source.read_text(), "bytes": prewarm_source.stat().st_size}
        report["sources"] = identify_sources(workloads, (prewarm_source,))
        expected, caches = {}, {}
        try:
            for workload in workloads:
                env = runtime_environment(base, workload)
                oracle = compiler if workload["name"] == "self" else python + [str(workload["source"])]
                records, expected[workload["name"]] = validate_application(oracle, workload, env, work, args.timeout)
                report["oracles"][workload["name"]] = records
                if args.cache != "cold":
                    cache = work / (workload["name"] + "-warm-cache")
                    cache.mkdir()
                    caches[workload["name"]] = cache
                    prewarm = execute(compiler + ["build", str(prewarm_source), "-o", str(work / "prewarm")],
                                      dict(env, PYSTACHY_CACHE=str(cache), PYSTACHY_BUILD_JOBS="1",
                                           PYSTACHY_LTO_PARTITIONS="0", PYSTACHY_TIMING="1"), args.timeout)
                    report["prewarm"].append({"workload": workload["name"],
                                              "source_sha256": report["prewarm_input"]["sha256"], **prewarm})
                    successful(prewarm)
                    if not list(cache.glob("runtime-py-*.bc")):
                        raise RuntimeError("prewarm did not publish runtime bitcode")
            states = ("cold", "warm") if args.cache == "both" else (args.cache,)
            for sample in range(args.samples):
                order = variants[sample % len(variants):] + variants[:sample % len(variants)]
                for workload in workloads:
                    for state in states:
                        for variant in order:
                            label = f"{workload['name']}-{state}-{variant['name']}-{sample}"
                            cold = work / (label + "-cache")
                            if state == "cold":
                                cold.mkdir()
                            cache = cold if state == "cold" else caches[workload["name"]]
                            executable = work / (label + ".exe")
                            env = runtime_environment(base, workload)
                            build = execute(compiler + ["build", str(workload["source"]), "-o", str(executable)],
                                            dict(env, PYSTACHY_CACHE=str(cache), PYSTACHY_TIMING="1",
                                                 PYSTACHY_BUILD_JOBS=str(variant["jobs"]),
                                                 PYSTACHY_LTO_PARTITIONS=str(variant["partitions"])), args.timeout)
                            row = {"workload": workload["name"], "cache": state, "variant": variant["name"],
                                   "sample": sample, "build": build, "application": [], "correct": False}
                            report["results"].append(row)
                            write_report(args.json, report)
                            successful(build)
                            build["stages"] = build_stages(build, variant, state)
                            row["binary_bytes"] = executable.stat().st_size
                            row["binary_sha256"] = file_digest(executable)
                            for _ in range(args.runtime_samples):
                                runs, actual = validate_application([str(executable)], workload, env, work, args.timeout)
                                row["application"].append(runs)
                                if actual != expected[workload["name"]]:
                                    raise RuntimeError(f"oracle mismatch: {label}; raw output is in --json")
                            row["correct"] = True
                            write_report(args.json, report)
                            print(f"{label}: build {build['wall_s']:.3f}s, CPU {build['cpu_s']:.3f}s, "
                                  f"tree RSS {build['sampled_process_tree_peak_rss_kib'] / 1024:.1f}MiB; output matched",
                                  file=sys.stderr, flush=True)
                            executable.unlink()
                            if state == "cold":
                                shutil.rmtree(cold)
            after = identify_sources(workloads, (prewarm_source,))
            if after["sha256"] != report["sources"]["sha256"]:
                raise RuntimeError("source inputs changed during measurement; discard timings")
            if command_identity(compiler) != report["compiler"]:
                raise RuntimeError("compiler executable changed during measurement; discard timings")
            report["status"] = "passed"
        except BaseException as error:
            report["status"] = "failed"
            report["failure"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            report["summary"] = summarize(report["results"])
            write_report(args.json, report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
