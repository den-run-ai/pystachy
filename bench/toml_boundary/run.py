"""Compare TOML containment costs in two source checkouts; no timing gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from ir_cost_report import inventory as ir_inventory  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, cwd, env, timeout):
    start = time.perf_counter()
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            raise RuntimeError(f"timeout: {command}\n{stderr[-2000:]}") from None
    result = {"command": command, "wall_s": time.perf_counter() - start,
              "stdout": stdout, "stderr": stderr, "returncode": proc.returncode}
    if proc.returncode:
        raise RuntimeError(f"failed: {command}\n{stdout[-1000:]}{stderr[-4000:]}")
    return result


def outputs(result, samples, checksum):
    lines = result["stdout"].splitlines()
    if len(lines) != samples:
        raise ValueError(f"wrong number of output rows: {lines}")
    times = []
    for line in lines:
        fields = line.split()
        if len(fields) != 3 or fields[0] != "sample" or int(fields[1]) != checksum:
            raise ValueError(f"CPython checksum mismatch: {line}")
        ns = int(fields[2])
        if ns <= 0:
            raise ValueError("nonpositive execution duration")
        times.append(ns / 1e9)
    result["in_process_samples_s"] = times
    return result


def inventory(path):
    raw = path.read_bytes()
    calls = ir_inventory(raw)["calls"]
    helpers = {name[1:]: count for name, count in calls.items() if name.startswith("@pys_dyn_")}
    generated = {name[1:]: count for name, count in calls.items() if name.startswith("@dyn.")}
    identity = {name[1:]: count for name, count in calls.items() if name.startswith("@pys_") and "identity" in name}
    return {"bytes": len(raw), "lines": len(raw.splitlines()),
            "sha256": digest(path), "dynamic_static_calls": dict(sorted(helpers.items())),
            "dynamic_static_calls_total": sum(helpers.values()),
            "generated_dynamic_static_calls": dict(sorted(generated.items())),
            "generated_dynamic_static_calls_total": sum(generated.values()),
            "identity_static_calls": dict(sorted(identity.items()))}


def manifest(root):
    # Include root entry points/C glue and extensionless library inputs, even
    # when untracked. This is a source manifest, not a hash of the host system.
    files = [path for path in root.iterdir() if path.is_file() and path.suffix in {".py", ".c", ".h"}]
    files.append(root / "tools/ir_cost_report.py")
    for folder in ("src", "lib", "ryu", "mpz"):
        files.extend(path for path in (root / folder).rglob("*")
                     if path.is_file() and "__pycache__" not in path.relative_to(root).parts
                     and path.suffix not in {".pyc", ".pyo"})
    return {str(path.relative_to(root)): digest(path) for path in sorted(files)}


def summarize(records, field):
    values = [record[field] for record in records]
    middle = statistics.median(values)
    return {"median_s": middle, "min_s": min(values), "max_s": max(values),
            "mad_s": statistics.median(abs(value - middle) for value in values)}


def summarize_process_samples(records):
    return summarize([{"median_s": statistics.median(record["in_process_samples_s"])}
                      for record in records], "median_s")


def retained_flags(header):
    # @extern("") resolves through the executable's dynamic symbol table.
    # Keep/export just the benchmark wrapper rather than every program symbol.
    if " " in str(header):
        raise ValueError("retained header path must not contain spaces")
    if sys.platform == "linux":
        export = "-Wl,--export-dynamic-symbol=toml_boundary_collect_live"
    elif sys.platform == "darwin":
        export = "-Wl,-exported_symbol,_toml_boundary_collect_live"
    else:
        raise ValueError("retained-memory probe supports Linux and macOS only")
    return "-include " + str(header) + " " + export


def retained_output(result, checksum, rounds):
    rows = result["stdout"].splitlines()
    if len(rows) != 2 or rows[0] != f"checksum {checksum}":
        raise ValueError("retention probe checksum differs")
    fields = rows[1].split()
    if len(fields) != 3 or fields[0] != "retained" or int(fields[2]) != checksum // rounds:
        raise ValueError("retained document changed after collection")
    live = int(fields[1])
    if live <= 0:
        raise ValueError("nonpositive retained-byte count")
    result["conservative_live_bytes"] = live
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="baseline source checkout")
    parser.add_argument("--candidate", type=Path, required=True, help="candidate source checkout")
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--processes", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    if min(args.width, args.rounds, args.samples, args.processes, args.timeout) <= 0:
        parser.error("work sizes, repetitions and timeout must be positive")
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        cpu = allowed[0] if args.cpu is None else args.cpu
        if cpu not in allowed:
            parser.error("selected CPU is outside this process's affinity")
        os.sched_setaffinity(0, {cpu})
    else:
        cpu = None
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME"}}
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env.update(PYTHONHASHSEED="0", PYSTACHY_PROGRAM_CACHE="0", PYSTACHY_JOBS="2")
    llvm = Path(env.get("PYSTACHY_LLVM", ""))
    runargs = [str(args.width), str(args.rounds), str(args.samples)]
    checksum = args.rounds * (args.width * (args.width + 1) // 2 + 23 * args.width)
    source = HERE / "consumer.py"
    oracle = outputs(execute([args.python, str(source)] + runargs, HERE, env, args.timeout),
                     args.samples, checksum)
    report = {
        "schema": 1, "status": "running", "platform": platform.platform(), "cpu": cpu,
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), "unknown") if Path("/proc/cpuinfo").exists() else "unknown",
        "python": execute([args.python, "--version"], HERE, env, args.timeout)["stdout"].strip(),
        "llvm": execute([str(llvm / "clang"), "--version"], HERE, env, args.timeout)["stdout"].strip(),
        "parameters": vars(args) | {"baseline": str(roots["baseline"]),
                                    "candidate": str(roots["candidate"]), "output": str(output)},
        "fixture_hashes": {path.name: digest(path) for path in sorted(HERE.iterdir()) if path.is_file()},
        "oracle": oracle, "variants": {},
        "limits": ["Shared-host timings are advisory; CPU pinning does not isolate the host.",
                   "IR counts are static calls before linking the runtime, not allocations or timings.",
                   "AOT C counters measure allocation requests, not physical traffic or all foreign allocations.",
                   "Post-collection live bytes use the conservative collector and retain source plus one document.",
                   "All compiler timings use the CPython-hosted compiler and this checkout's own libraries.",
                   "Initial builds use private empty runtime caches; later build/JIT samples use warm caches."],
    }

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    state = {}
    for tag, root in roots.items():
        directory = output / tag
        directory.mkdir()
        settings = dict(env, PYSTACHY_HOME=str(root), PYSTACHY_PATH=str(HERE),
                        PYSTACHY_CACHE=str(directory / "runtime"))
        command = [args.python, str(root / "pystachy.py")]
        ir = directory / "program.ll"
        optimized = directory / "program-O2.ll"
        binary = directory / "program"
        data = {
            "source_manifest": manifest(root),
            "revision": execute(["git", "rev-parse", "HEAD"], root, settings, args.timeout)["stdout"].strip(),
            "git_status": execute(["git", "status", "--porcelain"], root, settings, args.timeout)["stdout"],
            "environment": {key: value for key, value in settings.items() if key.startswith("PYSTACHY_")},
            "phases": {phase: [] for phase in ("frontend", "aot_build_warm", "jit", "aot")},
        }
        report["variants"][tag] = data
        data["frontend_prime"] = execute(command + ["ir", str(source), "-o", str(ir)], root, settings, args.timeout)
        data["ir"] = inventory(ir)
        data["llvm_program_optimize"] = execute([str(llvm / "opt"), "-S", "-O2", str(ir), "-o", str(optimized)],
                                                root, settings, args.timeout)
        data["optimized_program_ir"] = inventory(optimized)
        data["aot_build_cold"] = execute(command + ["build", str(source), "-o", str(binary)], root, settings, args.timeout)
        data["binary_bytes"] = binary.stat().st_size
        data["aot_prime"] = outputs(execute([str(binary)] + runargs, root, settings, args.timeout), args.samples, checksum)
        data["jit_prime"] = outputs(execute(command + ["run", str(source)] + runargs, root, settings, args.timeout),
                                    args.samples, checksum)
        state[tag] = (root, directory, settings, command, ir, binary)
        save()
    for repeat in range(args.processes):
        for tag in (["baseline", "candidate"] if repeat % 2 == 0 else ["candidate", "baseline"]):
            root, directory, settings, command, ir, binary = state[tag]
            phases = report["variants"][tag]["phases"]
            phases["frontend"].append(execute(command + ["ir", str(source), "-o", str(ir)], root, settings, args.timeout))
            phases["aot_build_warm"].append(execute(command + ["build", str(source), "-o", str(binary)], root, settings, args.timeout))
            for mode, cmd in (("jit", command + ["run", str(source)]), ("aot", [str(binary)])):
                phases[mode].append(outputs(execute(cmd + runargs, root, settings, args.timeout), args.samples, checksum))
            save()
    for tag in roots:
        root, directory, settings, command, ir, binary = state[tag]
        data = report["variants"][tag]
        counted = directory / "counted"
        counted_env = dict(settings, PYSTACHY_CFLAGS="-DPYSTACHY_PROFILE_DATA", PYSTACHY_CACHE=str(directory / "runtime-counted"))
        data["allocation_environment_overrides"] = {key: counted_env[key] for key in ("PYSTACHY_CFLAGS", "PYSTACHY_CACHE")}
        data["counted_build"] = execute(command + ["build", str(source), "-o", str(counted)], root, counted_env, args.timeout)
        data["allocation"] = outputs(execute([str(counted)] + runargs, root, counted_env, args.timeout), args.samples, checksum)
        lines = [line.removeprefix("pystachy-data: ") for line in data["allocation"]["stderr"].splitlines()
                 if line.startswith("pystachy-data: ")]
        if len(lines) != 1:
            raise ValueError("missing or duplicated allocation report")
        data["allocation"]["counters"] = json.loads(lines[0])
        retained = directory / "retained"
        # This header is only for ordinary AOT: JIT/extension glue is deliberately excluded.
        header = HERE / "retained.h"
        retained_env = dict(settings, PYSTACHY_CFLAGS=retained_flags(header),
                            PYSTACHY_CACHE=str(directory / "runtime-retained"))
        data["retained_environment_overrides"] = {key: retained_env[key] for key in ("PYSTACHY_CFLAGS", "PYSTACHY_CACHE")}
        data["retained_build"] = execute(command + ["build", str(HERE / "retained.py"), "-o", str(retained)],
                                          root, retained_env, args.timeout)
        data["retained_samples"] = [
            retained_output(execute([str(retained), str(args.width), str(args.rounds)], root, retained_env, args.timeout),
                            checksum, args.rounds) for _ in range(args.processes)
        ]
        data["retained"] = data["retained_samples"][0]
        live_samples = [sample["conservative_live_bytes"] for sample in data["retained_samples"]]
        median_live = statistics.median(live_samples)
        data["retained_summary"] = {"median_bytes": median_live, "min_bytes": min(live_samples),
                                    "max_bytes": max(live_samples),
                                    "mad_bytes": statistics.median(abs(value - median_live) for value in live_samples)}
        data["summary"] = {phase: summarize(records, "wall_s") for phase, records in data["phases"].items()}
        for mode in ("jit", "aot"):
            data["summary"][mode + "_in_process"] = summarize_process_samples(data["phases"][mode])
        if manifest(root) != data["source_manifest"]:
            raise RuntimeError(f"{tag} source changed during measurement")
        save()
    if {path.name: digest(path) for path in sorted(HERE.iterdir()) if path.is_file()} != report["fixture_hashes"]:
        raise RuntimeError("benchmark fixture changed during measurement")
    report["status"] = "complete"
    save()
    print(output / "report.json")


if __name__ == "__main__":
    main()
