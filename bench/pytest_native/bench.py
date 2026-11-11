"""Measure three qualified pytest suites, including preparation and edit/rebuild costs.

This is a process benchmark, not a CI timing gate. Every timed execution checks
its complete case inventory and runtime-derived checksums. The ordinary pytest
baseline has no custom reporting plugin; the independent oracle runs only in
the separately reported complete runner commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
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
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import pytest_native as runner  # noqa: E402 (script may run directly from any working directory)
from pytest_native_codegen import generate  # noqa: E402

SUITES = ("fixtures", "json_repair", "numeric")
VARIANTS = ("pytest", "generated_python", "native_jit", "native_aot")
PINNED_PYTHON = (ROOT / ".python-version").read_text().strip()
PINNED_PYTEST = "9.2.0"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measured(command, env, timeout, cwd=ROOT):
    """wait4 avoids polling quantization and measures each fresh child separately.

    ru_maxrss is the largest individual-process high-water mark accounted by
    wait4, including waited-for children, not simultaneous process-tree RSS.
    File-backed capture avoids deadlocks and preserves normal pipe buffering.
    """
    if not hasattr(os, "wait4") or not hasattr(signal, "setitimer"):
        raise RuntimeError("benchmark requires POSIX wait4 and interval timers")
    before = list(os.getloadavg())
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        start = time.perf_counter()
        process = subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        def timed_out(signum, frame):
            raise TimeoutError(f"process exceeded {timeout:g}s")
        old_handler = signal.signal(signal.SIGALRM, timed_out)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        error = ""
        try:
            _, status, usage = os.wait4(process.pid, 0)
        except BaseException as failure:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, status, usage = os.wait4(process.pid, 0)
            if not isinstance(failure, TimeoutError):
                raise
            error = str(failure)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
        elapsed = time.perf_counter() - start
        process.returncode = os.waitstatus_to_exitcode(status)
        stdout.seek(0)
        stderr.seek(0)
        record = {
            "command": command, "cwd": str(cwd), "seconds": elapsed,
            "returncode": process.returncode,
            "peak_rss_bytes": usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024),
            "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
            "stdout": stdout.read().decode("utf-8", errors="replace"),
            "stderr": stderr.read().decode("utf-8", errors="replace"),
            "load_before": before, "load_after": list(os.getloadavg()),
        }
        if error:
            record["error"] = error
        return record


def checked(record):
    if record["returncode"] or "error" in record:
        raise ValueError("command failed: " + shlex.join(record["command"]) + "\n"
                         + record.get("error", "") + "\n" + record["stderr"] + record["stdout"])


def environment(input_path, cache, program_cache="0"):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTHON", "PYTEST", "PYSTACHY")) or key == "PYSTACHY_LLVM"}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PATH=str(ROOT / "ports"),
               PYTHONPATH=str(ROOT / "ports"), PYSTACHY_CACHE=str(cache), PYSTACHY_JOBS="1",
               PYSTACHY_PROGRAM_CACHE=program_cache, PYTEST_BENCH_INPUT=str(input_path),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONHASHSEED="0", PYTHONNOUSERSITE="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", LC_ALL="C", COLUMNS="80")
    return env


def expected_checksums(name, input_path, revision=0):
    rows = input_path.read_text().splitlines()
    if name == "fixtures":
        values = [2 * int(rows[0]) + 2 * index for index in range(16)]
    elif name == "json_repair":
        values = [int(row.split("\t")[0]) * len(row.split("\t")[2]) for row in rows]
    else:
        values = [int(row.split("\t")[3]) for row in rows]
    return [(str(index), str(value + revision)) for index, value in enumerate(values)]


def validate_checksums(stdout, expected):
    actual = re.findall(r"\bBENCH ([0-9]+) ([0-9]+)(?=\s|$)", stdout)
    if actual != expected:
        raise ValueError(f"case/checksum inventory differs: {actual!r} != {expected!r}")


def validate_generated(record, report, cases, checksums):
    checked(record)
    events = runner.read_report(report, cases, record["returncode"])
    if len(events) != 3 * len(cases) or any(event["outcome"] != "passed" for event in events):
        raise ValueError("every case and setup/call/teardown phase must pass")
    validate_checksums(record["stdout"], checksums)


def validate_pytest(record, checksums):
    checked(record)
    matches = re.findall(r"(?:^|\n)([0-9]+) passed in ", record["stdout"])
    if matches != [str(len(checksums))]:
        raise ValueError("ordinary pytest must report the exact all-passed case count")
    validate_checksums(record["stdout"], checksums)


def pytest_command(python, source, config):
    # Deliberately no -p _pyn_oracle or other custom reporting plugin. -s makes
    # the same small checksum output observable in all four timed variants.
    return [python, "-m", "pytest", "-q", "-s", "-p", "no:cacheprovider", "--noconftest",
            "--rootdir", str(ROOT), "-c", str(config), str(source)]


def prepare(source, output):
    output.mkdir(parents=True, exist_ok=False)
    generated = generate(source.read_text(), source.relative_to(ROOT).as_posix())
    path = output / "generated.py"
    path.write_text(generated.source)
    shutil.copyfile(ROOT / "tools/pytest_native_support.py", output / "pytest_native_support.py")
    info = {"source": str(path), "cases": generated.cases,
            "generated_sha256": digest(path),
            "support_sha256": digest(output / "pytest_native_support.py")}
    (output / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


def complete_command(source, mode, work, args, env, checksums):
    work.mkdir(parents=True, exist_ok=True)
    evidence_path = work / "result.json"
    evidence_path.unlink(missing_ok=True)
    root = ROOT if source.is_relative_to(ROOT) else source.parent
    command = [args.python, str(ROOT / "tools/pytest_native.py"), str(source), "--root", str(root),
               "--mode", mode, "--compiler", args.compiler, "--python", args.python,
               "--work-dir", str(work), "--json", str(evidence_path), "--compare",
               "--timeout", str(args.timeout)]
    record = measured(command, env, 3 * args.timeout + 30)
    checked(record)
    evidence = json.loads(evidence_path.read_text())
    expected = generate(source.read_text(), source.relative_to(root).as_posix()).cases
    results = [runner.Result(**result) for result in evidence["results"]]
    if (evidence["exit_code"] != 0 or evidence["mode"] != mode
            or [case for result in results for case in result.cases] != expected
            or not evidence.get("oracle") or runner.compare(results, evidence["oracle"])
            or any(result.state != "passed" or any(event["outcome"] != "passed" for event in result.events)
                   for result in results)):
        raise ValueError("full runner command failed original-pytest qualification")
    validate_checksums("".join(result.stdout for result in results), checksums)
    record["evidence"] = evidence
    record["cache_policy"] = "program cache enabled; private runtime/program cache for this mode"
    return record


def percentile(values, fraction):
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = math.floor(rank)
    upper = math.ceil(rank)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def distribution(records):
    values = [record["seconds"] for record in records]
    return {"count": len(values), "median_seconds": statistics.median(values),
            "min_seconds": min(values), "p10_seconds": percentile(values, 0.1),
            "p90_seconds": percentile(values, 0.9), "max_seconds": max(values),
            "stdev_seconds": statistics.stdev(values) if len(values) > 1 else 0.0,
            "max_peak_rss_bytes": max(record["peak_rss_bytes"] for record in records)}


def break_even(upfront, baseline, native):
    saving = baseline - native
    return max(1, math.ceil(upfront / saving)) if saving > 0 else None


def benchmark_suite(name, args, result, checkpoint):
    directory = args.work_dir / name
    directory.mkdir()
    source = HERE / ("test_" + name + ".py")
    input_path = HERE / "inputs" / (name + (".txt" if name == "fixtures" else ".tsv"))
    checksums = expected_checksums(name, input_path)
    result.update(suite=name, source=source.relative_to(ROOT).as_posix(), source_sha256=digest(source),
                  input=input_path.relative_to(ROOT).as_posix(), input_sha256=digest(input_path),
                  checksums=checksums, cases=len(checksums))
    result["complete_commands"] = {}
    # Qualify all modes before collecting comparative timings. These are also
    # actual complete first commands, with the default independent oracle.
    for mode in ("python", "jit", "aot"):
        env = environment(input_path, directory / ("full-cache-" + mode), "1")
        work = directory / ("full-" + mode)
        print(f"{name}: first complete {mode} command (cold private cache)", flush=True)
        first = complete_command(source, mode, work, args, env, checksums)
        unchanged = complete_command(source, mode, work, args, env, checksums)
        result["complete_commands"][mode] = {"first": first, "unchanged": unchanged}
        checkpoint()
    prepared = directory / "prepared"
    env = environment(input_path, directory / "sample-cache")
    prep = measured([args.python, str(Path(__file__).resolve()), "_prepare", str(source), str(prepared)],
                    env, args.timeout)
    checked(prep)
    manifest = json.loads((prepared / "manifest.json").read_text())
    if len(manifest["cases"]) != len(checksums):
        raise ValueError("prepared case inventory differs")
    result["preparation"] = prep
    result["generated"] = manifest
    generated = Path(manifest["source"])
    executable = prepared / "suite"
    compiler = shlex.split(args.compiler)
    result["build"] = measured([*compiler, "build", str(generated), "-o", str(executable)],
                               env, args.timeout)
    checked(result["build"])
    result["executable_sha256"] = digest(executable)
    checkpoint()
    config = directory / "empty.ini"
    config.write_text("[pytest]\n")
    report = prepared / "events.jsonl"
    commands = {
        "pytest": pytest_command(args.python, source, config),
        "generated_python": [args.python, str(generated), str(report)],
        "native_jit": [*compiler, "run", str(generated), str(report)],
        "native_aot": [str(executable), str(report)],
    }
    # AOT does not necessarily populate JIT's runtime object, shared runtime or
    # LLJIT launcher. Keep this initial JIT setup out of warm-runtime samples,
    # but record and validate its complete elapsed time and resource cost.
    report.unlink(missing_ok=True)
    print(f"{name}: preparing JIT-specific runtime artifacts", flush=True)
    warmup = measured(commands["native_jit"], env, args.timeout)
    validate_generated(warmup, report, manifest["cases"], checksums)
    result["jit_runtime_warmup"] = warmup
    checkpoint()
    samples = {name: [] for name in VARIANTS}
    result["samples"] = samples
    result["sample_order"] = []
    rng = random.Random(args.order_seed)
    for index in range(args.samples):
        order = list(VARIANTS)
        rng.shuffle(order)
        for variant in order:
            print(f"{name}: sample {index + 1}/{args.samples} {variant}", flush=True)
            report.unlink(missing_ok=True)
            record = measured(commands[variant], env, args.timeout)
            record["round"] = index
            samples[variant].append(record)
            result["sample_order"].append(variant)
            if variant == "pytest":
                validate_pytest(record, checksums)
            else:
                validate_generated(record, report, manifest["cases"], checksums)
        checkpoint()
    result["distributions"] = {name: distribution(rows) for name, rows in samples.items()}
    medians = {name: summary["median_seconds"] for name, summary in result["distributions"].items()}
    result["aot_break_even_runs"] = {
        "versus_pytest": break_even(prep["seconds"] + result["build"]["seconds"],
                                   medians["pytest"], medians["native_aot"]),
        "versus_prepared_python": break_even(result["build"]["seconds"],
                                            medians["generated_python"], medians["native_aot"]),
    }
    # This is a semantic source edit, not a comment touch: both the executed
    # checksum and expectation change. A stale native executable cannot pass.
    edited_dir = directory / "edited"
    edited_dir.mkdir()
    edited = edited_dir / source.name
    original = source.read_text()
    if original.count("REVISION = 0") != 1:
        raise ValueError("missing unique semantic edit marker")
    edited.write_text(original.replace("REVISION = 0", "REVISION = 1"))
    result["edited_source_sha256"] = digest(edited)
    edited_checksums = expected_checksums(name, input_path, 1)
    for mode in ("python", "jit", "aot"):
        env = environment(input_path, directory / ("full-cache-" + mode), "1")
        print(f"{name}: edited complete {mode} command", flush=True)
        # Keep the same input path and generated work paths for a real cache
        # invalidation check; restore our temporary copy afterwards.
        mutable_source = directory / "live" / source.name
        mutable_source.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, mutable_source)
        live_work = directory / ("edit-" + mode)
        complete_command(mutable_source, mode, live_work, args, env, checksums)
        mutable_source.write_text(edited.read_text())
        row = complete_command(mutable_source, mode, live_work, args, env, edited_checksums)
        result["complete_commands"][mode]["edited"] = row
        checkpoint()
    return result


def provenance(args):
    def output(command):
        return subprocess.check_output(command, cwd=ROOT, text=True).strip()
    paths = set(ROOT.glob("*.py")) | set(HERE.glob("*.py")) | set((HERE / "inputs").iterdir())
    for directory in ("src", "lib", "ports"):
        paths.update((ROOT / directory).rglob("*.py"))
    paths.update((ROOT / "tools").glob("pytest_native*.py"))
    for directory in ("runtime.c", "runtime.py", "ryu", "mpz"):
        path = ROOT / directory
        if path.is_file():
            paths.add(path)
        elif path.is_dir():
            paths.update(p for p in path.rglob("*") if p.is_file() and p.suffix in {".c", ".h"})
    versions = json.loads(output([args.python, "-c", "import json,platform,pytest; print(json.dumps("
                                 "{'python':platform.python_version(),'pytest':pytest.__version__}))"]))
    if versions != {"python": PINNED_PYTHON, "pytest": PINNED_PYTEST}:
        raise ValueError(f"use pinned Python {PINNED_PYTHON} and pytest {PINNED_PYTEST}; got {versions}")
    compiler = shlex.split(args.compiler)
    compiler_path = Path(shutil.which(compiler[0]) or compiler[0]).resolve()
    llvm = {}
    for tool in ("clang", "opt", "llc"):
        prefix = os.environ.get("PYSTACHY_LLVM", "")
        path = Path(prefix) / tool if prefix else Path(shutil.which(tool) or tool)
        if path.is_file():
            llvm[tool] = {"path": str(path.resolve()), "sha256": digest(path),
                          "version": output([str(path), "--version"]).splitlines()[0]}
    cpuinfo = Path("/proc/cpuinfo")
    cpu = next((line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                if line.startswith("model name")), "unknown") if cpuinfo.exists() else platform.processor()
    return {"git_commit": output(["git", "rev-parse", "HEAD"]),
            "git_status": output(["git", "status", "--short", "--untracked-files=all"]),
            "source_sha256": {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(paths)},
            "compiler_command": compiler, "compiler_executable_sha256": digest(compiler_path),
            "platform": platform.platform(), "cpu": cpu, "versions": versions,
            "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "llvm": os.environ.get("PYSTACHY_LLVM", "system PATH"),
            "llvm_tools": llvm,
            "ld_library_path": os.environ.get("LD_LIBRARY_PATH", ""),
            "samples": args.samples, "order_seed": args.order_seed,
            "process_memory": "wait4 maximum individual-process RSS, not concurrent process-tree sum",
            "sample_policy": "fresh processes; fixed shuffled order; program cache disabled; runtime cache warm",
            "complete_command_policy": "default original-pytest oracle included; private caches; program cache enabled",
            "cold_definition": "empty Pystachy cache; OS page cache and installed Python pycs are not cleared",
            "environment": {key: value for key, value in environment(Path("INPUT"), Path("CACHE")).items()
                            if key.startswith(("PYSTACHY_", "PYTHON", "PYTEST_")) or key in {"LC_ALL", "COLUMNS"}}}


def markdown(data):
    rows = ["# Native pytest multi-suite measurements", "",
            "Measured test bodies and generated collection/dispatch on the same pinned inputs. "
            "These original benchmark suites do not claim full upstream pytest or package compatibility.", "",
            "Ordinary pytest uses no diagnostic reporting plugin. Native JIT samples include fresh program "
            "compilation with a warm runtime cache; AOT samples use a prebuilt executable. "
            "Complete runner commands below include the independent CPython pytest oracle "
            "and explicitly enable the program cache.", "",
            "| Suite | Cases | Ordinary pytest | Generated CPython | Native JIT | Prebuilt AOT | AOT speedup |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for suite in data["suites"]:
        stats = suite["distributions"]
        med = {name: value["median_seconds"] for name, value in stats.items()}
        times = " | ".join(f"{1000 * med[name]:.2f} ms" for name in VARIANTS)
        rows.append(f"| {suite['suite']} | {suite['cases']} | {times} | {med['pytest'] / med['native_aot']:.2f}× |")
    for suite in data["suites"]:
        rows += ["", "## " + suite["suite"], "", "All timings include process startup. "
                 "Each sampled execution passed the exact case/checksum inventory; generated runs also "
                 "passed every setup, call and teardown phase.", "",
                 "| Execution | Median | p10–p90 | Min–max | Peak individual-process RSS |",
                 "|---|---:|---:|---:|---:|"]
        for name, stats in suite["distributions"].items():
            rows.append(f"| {name} | {stats['median_seconds'] * 1000:.2f} ms | "
                        f"{stats['p10_seconds'] * 1000:.2f}–{stats['p90_seconds'] * 1000:.2f} ms | "
                        f"{stats['min_seconds'] * 1000:.2f}–{stats['max_seconds'] * 1000:.2f} ms | "
                        f"{stats['max_peak_rss_bytes'] / 1048576:.1f} MiB |")
        prep, build = suite["preparation"]["seconds"], suite["build"]["seconds"]
        rows += ["", f"Preparation: **{prep:.3f} s**; standalone AOT build: **{build:.3f} s** "
                 f"({suite['build']['peak_rss_bytes'] / 1048576:.1f} MiB peak individual-process RSS).",
                 "", f"Initial JIT execution to populate JIT-specific runtime artifacts: "
                 f"**{suite['jit_runtime_warmup']['seconds']:.3f} s** (recorded separately; "
                 "the cache already contains artifacts from the AOT build).",
                 "", "Each lifecycle value below is one observation, not a timing distribution.", "",
                 "| Full runner command, oracle + program cache | First, cold cache | Unchanged rerun | Semantic edit/rebuild |",
                 "|---|---:|---:|---:|"]
        for mode, values in suite["complete_commands"].items():
            rows.append(f"| {mode} | " + " | ".join(f"{values[key]['seconds']:.3f} s"
                                                    for key in ("first", "unchanged", "edited")) + " |")
        breakeven = suite["aot_break_even_runs"]
        rows += ["", "AOT break-even (preparation/build amortized, using measured medians): "
                 f"**{breakeven['versus_pytest']} runs** versus ordinary pytest; "
                 f"**{breakeven['versus_prepared_python']} runs** versus prepared CPython. "
                 "`None` means no measured per-run saving. This excludes the separately reported "
                 "qualification oracle and assumes unchanged tests."]
    meta = data["metadata"]
    rows += ["", "## Reproduction and limits", "", f"Commit: `{meta['git_commit']}`. "
             f"Python {meta['versions']['python']}; pytest {meta['versions']['pytest']}. "
             f"{meta['cpu']}; {meta['platform']}; CPU affinity {meta['cpu_affinity']}. "
             f"{meta['samples']} interleaved samples per execution; shuffle seed {meta['order_seed']}.", "",
             "The adjacent JSON records exact commands, source/input/compiler hashes, raw samples, "
             "phase outcomes, checksums, load averages, environment and first-command build/run times. "
             "Peak RSS is the largest individual-process high-water mark from wait4, not a sum of "
             "concurrent processes. Cold means an empty private Pystachy cache; filesystem page caches "
             "and installed Python bytecode caches remain uncontrolled. Shared-host load can affect results.", "",
             "The fixture suite is intentionally small, JSON repair uses the maintained adapted port "
             "under both interpreters, and the numeric suite is a typed integer-loop workload. "
             "No combined average is meaningful across these different workloads. See README.md for "
             "the replay command and input definitions.", ""]
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=SUITES, action="append")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--order-seed", type=int, default=20261110)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--work-dir", type=Path, required=True, help="must not already exist")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.samples < 3 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("use at least three samples and a finite positive timeout")
    selected = args.suite or list(SUITES)
    if len(selected) != len(set(selected)):
        parser.error("suite selections must be unique")
    if hasattr(os, "sched_getaffinity"):
        allowed = os.sched_getaffinity(0)
        cpu = min(allowed) if args.cpu is None else args.cpu
        if cpu not in allowed:
            parser.error("selected CPU is outside this process's allowed affinity")
        os.sched_setaffinity(0, {cpu})
    elif args.cpu is not None:
        parser.error("CPU pinning is unavailable on this platform")
    args.work_dir = args.work_dir.resolve()
    args.work_dir.mkdir(parents=True, exist_ok=False)
    data = {"schema": 1, "complete": False, "metadata": provenance(args), "suites": []}
    def save():
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    save()
    try:
        for name in selected:
            result = {}
            data["suites"].append(result)
            benchmark_suite(name, args, result, save)
            save()
        after = provenance(args)
        for key in ("source_sha256", "compiler_executable_sha256", "llvm_tools"):
            if data["metadata"][key] != after[key]:
                raise ValueError(f"benchmark inputs changed during measurement: {key}")
        data["metadata"]["measured_sources_unchanged"] = True
        data["complete"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        data["error"] = str(error)
        print(str(error), file=sys.stderr)
        save()
        return 1
    save()
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(data))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "_prepare":
        print(json.dumps(prepare(Path(sys.argv[2]), Path(sys.argv[3]))))
    else:
        raise SystemExit(main())
