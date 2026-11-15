"""Measure stored iterator dispatch, construction and specialization growth."""
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
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ir_cost_report import inventory  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, root, env, timeout):
    started = time.perf_counter()
    with subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError(f"command timed out: {command}") from None
    if process.returncode:
        raise RuntimeError(f"command failed: {command}\n{stdout[-1000:]}{stderr[-4000:]}")
    return {"command": command, "wall_s": time.perf_counter() - started,
            "stdout": stdout, "stderr": stderr}


def workload(mode, implementations, consumers):
    """Keep the operation sequence identical; vary only its storage boundary."""
    lines = ["import sys", "from time import perf_counter_ns"]
    if mode == "stored":
        lines.append("from adapter import TypedIterator, int_iterator")
    for index in range(implementations):
        lines.extend([
            "", "", f"class Cursor{index}:",
            "    def __init__(self, size: int, seed: int) -> None:",
            "        self.size = size", "        self.seed = seed", "        self.index = 0",
            "", "    def __iter__(self):", "        return self", "",
            "    def __next__(self) -> int:", "        if self.index == self.size:",
            "            raise StopIteration", "        self.index += 1",
            f"        return self.index * 3 + self.seed + {index}",
        ])
    annotation = ": TypedIterator[int]" if mode == "stored" else ": Cursor0 | Cursor1" if mode == "union" else ""
    for index in range(consumers):
        lines.extend([
            "", "", f"def consume{index}(source{annotation}) -> int:",
            "    total = 0", "    while True:", "        try:",
            "            value = source.__next__()", "        except StopIteration:",
            "            break", f"        total = (total * 33 + value + {index}) % 1000000007",
            "    return total",
        ])
    lines.extend(["", "", "def run(size: int, rounds: int) -> int:", "    checksum = 0", "    for repeat in range(rounds):"])
    for consumer in range(consumers):
        for implementation in range(implementations):
            value = f"Cursor{implementation}(size, repeat)"
            if mode == "stored":
                value = f"int_iterator({value})"
            lines.append(f"        checksum += consume{consumer}({value})")
    lines.extend([
        "    return checksum", "", "", "size = int(sys.argv[1])", "rounds = int(sys.argv[2])",
        "started = perf_counter_ns()", "checksum = run(size, rounds)",
        "elapsed = perf_counter_ns() - started", 'print("sample", checksum, elapsed)', "",
    ])
    return "\n".join(lines)


def read_sample(result, expected=None):
    fields = result["stdout"].split()
    if len(fields) != 3 or fields[0] != "sample":
        raise ValueError(f"unexpected output: {result['stdout']}")
    checksum, elapsed = int(fields[1]), int(fields[2])
    if expected is not None and checksum != expected:
        raise ValueError(f"checksum {checksum} differs from CPython {expected}")
    if elapsed <= 0:
        raise ValueError("nonpositive workload duration")
    return result | {"checksum": checksum, "work_s": elapsed / 1e9}


def summary(records, field):
    values = [record[field] for record in records]
    median = statistics.median(values)
    return {"median_s": median, "min_s": min(values), "max_s": max(values),
            "mad_s": statistics.median(abs(value - median) for value in values)}


def source_manifest(root):
    files = [path for path in root.iterdir() if path.is_file() and path.suffix in {".py", ".c", ".h"}]
    files.append(root / "VERSION")
    for folder in ("src", "lib", "ryu", "mpz", "examples/typed_iterator"):
        files.extend(path for path in (root / folder).rglob("*") if path.is_file()
                     and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"})
    return {str(path.relative_to(root)): digest(path) for path in sorted(files)}


def ir_summary(path):
    result = inventory(path.read_bytes())
    consumers = {name: data for name, data in result["functions"].items() if name.startswith("f.consume")}
    return {name: result[name] for name in ("sha256", "bytes", "lines", "defined_functions")} | {
        "consumer_bodies": len(consumers), "consumer_symbols": sorted(consumers),
        "indirect_call_sites": result["calls"].get("<indirect>", 0),
        "dynamic_helper_call_sites": {name: count for name, count in result["calls"].items()
                                      if name.startswith(("@pys_dyn_", "@dyn."))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--shapes", default="2x1,8x8", help="implementations x consumers, comma separated")
    parser.add_argument("--items", type=int, default=2048)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--construction-rounds", type=int, default=500)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--build-samples", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--skip-allocations", action="store_true")
    parser.add_argument("--jit", action="store_true", help="also measure JIT launch and in-process work")
    args = parser.parse_args()
    try:
        shapes = [tuple(int(value) for value in shape.split("x")) for shape in args.shapes.split(",")]
        if not shapes or any(len(shape) != 2 or min(shape) <= 0 for shape in shapes):
            raise ValueError
    except ValueError:
        parser.error("--shapes requires positive pairs such as 2x1,8x8")
    if min(args.items, args.rounds, args.construction_rounds, args.samples, args.build_samples, args.timeout) <= 0:
        parser.error("work sizes, repetitions and timeout must be positive")
    if len(set(shapes)) != len(shapes):
        parser.error("--shapes contains duplicates")
    root, output = args.checkout.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cpu = None
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        cpu = allowed[0] if args.cpu is None else args.cpu
        if cpu not in allowed:
            parser.error("--cpu is outside the available affinity")
        os.sched_setaffinity(0, {cpu})
    elif args.cpu is not None:
        parser.error("CPU affinity is unavailable on this platform")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME"}}
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_PATH=str(root / "examples/typed_iterator"),
               PYTHONPATH=str(root / "examples/typed_iterator"), PYTHONHASHSEED="0",
               PYSTACHY_JOBS="2", PYSTACHY_PROGRAM_CACHE="0")
    command = [args.python, str(root / "pystachy.py")]
    llvm = Path(env.get("PYSTACHY_LLVM", ""))
    cases = {"dispatch": [str(args.items), str(args.rounds)],
             "construction": ["1", str(args.construction_rounds)]}
    report = {
        "schema": 1, "status": "running", "platform": platform.platform(), "cpu": cpu,
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), "unknown") if Path("/proc/cpuinfo").exists() else "unknown",
        "python": execute([args.python, "--version"], root, env, args.timeout)["stdout"].strip(),
        "llvm": execute([str(llvm / "clang"), "--version"], root, env, args.timeout)["stdout"].strip(),
        "revision": execute(["git", "rev-parse", "HEAD"], root, env, args.timeout)["stdout"].strip(),
        "git_status": execute(["git", "status", "--porcelain"], root, env, args.timeout)["stdout"],
        "source_manifest": source_manifest(root), "runner_sha256": digest(Path(__file__)),
        "inventory_tool_sha256": digest(ROOT / "tools/ir_cost_report.py"),
        "parameters": vars(args) | {"checkout": str(root), "output": str(output)}, "variants": {},
        "limits": [
            "Synthetic consumers measure a storage tradeoff, not package compatibility or application speedup.",
            "Timings use one pinned core on a shared host; affinity does not isolate other workloads.",
            "Compiler timings use CPython-hosted compilation; initial builds use empty private runtime caches.",
            "IR counts are static, before runtime linking; LLVM may inline or merge bodies later.",
            "Allocation counters include process setup/shutdown and C GC requests before allocator rounding.",
            "Counted AOT runs are separate from timings; foreign allocations and JIT fast allocations are excluded.",
            "One-item construction cases also consume and exhaust each iterator; they are not allocation-only timings.",
        ],
    }

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    state = {}
    checksums = {}
    for implementations, consumers in shapes:
        for mode in ("specialized", "stored", "union") if implementations == 2 else ("specialized", "stored"):
            tag = f"{implementations}x{consumers}-{mode}"
            directory = output / tag
            directory.mkdir()
            source, ir, binary = directory / "workload.py", directory / "program.ll", directory / "program"
            source.write_text(workload(mode, implementations, consumers))
            settings = dict(env, PYSTACHY_CACHE=str(directory / "runtime"))
            data = {"implementations": implementations, "consumers": consumers, "mode": mode,
                    "workload_sha256": digest(source), "oracles": {}, "frontend": [], "build": [], "runs": {}}
            report["variants"][tag] = data
            for case, parameters in cases.items():
                oracle = read_sample(execute([args.python, str(source)] + parameters, root, settings, args.timeout))
                key = (implementations, consumers, case)
                expected = checksums.setdefault(key, oracle["checksum"])
                if oracle["checksum"] != expected:
                    raise ValueError(f"CPython variants disagree: {tag} {case}")
                data["oracles"][case] = oracle
                data["runs"][case] = {"aot": [], "jit": []}
            data["frontend_prime"] = execute(command + ["ir", str(source), "-o", str(ir)], root, settings, args.timeout)
            data["ir"] = ir_summary(ir)
            data["build_cold"] = execute(command + ["build", str(source), "-o", str(binary)], root, settings, args.timeout)
            data["binary_bytes"] = binary.stat().st_size
            data["binary_sha256"] = digest(binary)
            for case, parameters in cases.items():
                read_sample(execute([str(binary)] + parameters, root, settings, args.timeout), data["oracles"][case]["checksum"])
            state[tag] = (source, ir, binary, settings)
            save()
    tags = list(state)
    for sample in range(max(args.samples, args.build_samples)):
        order = tags[sample % len(tags):] + tags[:sample % len(tags)]
        if sample % 2:
            order.reverse()
        for tag in order:
            source, ir, binary, settings = state[tag]
            data = report["variants"][tag]
            if sample < args.build_samples:
                data["frontend"].append(execute(command + ["ir", str(source), "-o", str(ir)], root, settings, args.timeout))
                data["build"].append(execute(command + ["build", str(source), "-o", str(binary)], root, settings, args.timeout))
            if sample < args.samples:
                for case, parameters in cases.items():
                    expected = data["oracles"][case]["checksum"]
                    data["runs"][case]["aot"].append(read_sample(execute([str(binary)] + parameters, root, settings, args.timeout), expected))
                    if args.jit:
                        data["runs"][case]["jit"].append(read_sample(execute(command + ["run", str(source)] + parameters, root, settings, args.timeout), expected))
            save()
    for tag in tags:
        source, ir, binary, settings = state[tag]
        data = report["variants"][tag]
        data["summary"] = {"frontend": summary(data["frontend"], "wall_s"), "build_warm": summary(data["build"], "wall_s")}
        for case, modes in data["runs"].items():
            data["summary"][case] = {mode: {"process": summary(records, "wall_s"), "work": summary(records, "work_s")}
                                     for mode, records in modes.items() if records}
        if not args.skip_allocations:
            counted = binary.with_name("counted")
            counted_env = dict(settings, PYSTACHY_CFLAGS="-DPYSTACHY_PROFILE_DATA",
                               PYSTACHY_CACHE=str(binary.parent / "runtime-counted"))
            data["counted_build"] = execute(command + ["build", str(source), "-o", str(counted)], root, counted_env, args.timeout)
            data["counted_binary_sha256"] = digest(counted)
            data["allocations"] = {}
            for case, parameters in cases.items():
                result = read_sample(execute([str(counted)] + parameters, root, counted_env, args.timeout), data["oracles"][case]["checksum"])
                rows = [line.removeprefix("pystachy-data: ") for line in result["stderr"].splitlines() if line.startswith("pystachy-data: ")]
                if len(rows) != 1:
                    raise ValueError("missing or duplicate allocation report")
                data["allocations"][case] = result | {"counters": json.loads(rows[0]),
                    "iterator_constructions": data["implementations"] * data["consumers"] * int(parameters[1])}
        if digest(source) != data["workload_sha256"]:
            raise RuntimeError(f"generated workload changed: {source}")
        save()
    if (source_manifest(root) != report["source_manifest"] or digest(Path(__file__)) != report["runner_sha256"]
            or digest(ROOT / "tools/ir_cost_report.py") != report["inventory_tool_sha256"]):
        raise RuntimeError("source changed during measurement")
    report["status"] = "complete"
    save()
    print(output / "report.json")


if __name__ == "__main__":
    main()
