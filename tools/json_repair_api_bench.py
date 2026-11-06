"""Measure the installed CPython repair API after exact cross-backend checks.

Use the interpreter in which the companion wheel is installed. Upstream must be
an unmodified checkout of the version pinned by the parity corpus. Each backend
runs in its own isolated process; see bench/json_repair/README.md for scopes.
"""
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

# -I removes the script directory. These are repository-owned evidence helpers,
# not import roots for either repair backend.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from json_repair_bench import digest, source_identity
from json_repair_parity import exact_equal

ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATHS = tuple(Path(path).resolve() for path in
                      (__file__, source_identity.__code__.co_filename, exact_equal.__code__.co_filename))
BACKENDS = ("upstream", "adapted", "installed")
APIS = ("text", "objects", "logs")
CALIBRATION_STEPS = 8
CALIBRATION_ROUNDS = 1_000_000


def workloads():
    """Constructed trace-like records; proportions are choices, not field data."""
    valid = [
        '{"role":"assistant","tool_calls":[{"name":"search","arguments":{"query":"東京 café","limit":3}}],"ok":true}',
        '{"role":"verifier","ok":false,"reward":-0.0,"attempt":9223372036854775808,"reason":null}',
        '{"state":{"position":[1.25,-3,0],"actions":["left","right"],"done":false},"seed":18446744073709551616}',
        '{"candidates":[{"text":"naïve façade","score":0.75},{"text":"界","score":0.5}],"selected":0}',
        '{"role":"assistant","code":"def f(x):\\n    return x + 1\\n","path":"src/main.py","ok":true}',
        '{"tool":"search","arguments":"{\\"query\\":\\"redwoods\\",}","ok":true}',
        '{"result":{"items":[true,1,1.0,null,"",[],{}],"nested":{"child":{"value":42}}}}',
        json.dumps({"answer": "A useful explanation. " * 96, "citations": [1, 2], "ok": True}),
    ]
    malformed = [
        '{role: assistant, tool_calls: [{name: search, arguments: {query: 東京 café, limit: 3}}], ok: true}',
        '{"role":"verifier" "ok":false "reward":-0.0 "attempt":9223372036854775808 "reason":null}',
        '{"state":{"position":[1.25,-3,0,],"actions":["left","right"],"done":false},"seed":18446744073709551616,}',
        '```json\n{"candidates":[{"text":"naïve façade","score":0.75},{"text":"界","score":0.5}],"selected":0}\n```',
        '{"role":"assistant","code":"def f(x):\n    return x + 1\n","path":"src/main.py","ok":true}',
        "{tool: 'search', arguments: '{\"query\":\"redwoods\",}', ok: True}",
        '{"result":{"items":[true,1,1.0,null,"",[],{}],"nested":{"child":{"value":42}}}',
        '{answer: ' + json.dumps("A useful explanation. " * 96) + ', citations: [1,2], ok: true}',
    ]
    # Each source occurs in the 80/20 mix, avoiding a different input-shape mix
    # between the all-valid/all-malformed controls and the combined workload.
    return {"valid": valid, "malformed": malformed,
            "mixed": [source for pair in zip(valid, malformed) for source in [pair[0]] * 4 + [pair[1]]]}


def tagged(value):
    """Preserve bool/int, signed zero, container type/order and exact code points."""
    kind = type(value)
    if value is None:
        return ["none"]
    if kind is bool:
        return ["bool", value]
    if kind is int:
        return ["int", str(value)]
    if kind is float:
        return ["float", value.hex()]
    if kind is str:
        return ["str", [ord(char) for char in value]]
    if kind in (list, tuple):
        return [kind.__name__, [tagged(item) for item in value]]
    if kind is dict:
        return ["dict", [[tagged(key), tagged(item)] for key, item in value.items()]]
    raise TypeError(f"unexpected repair result type: {kind.__name__}")


def invoke(module, api, source, *, forced=False):
    if api == "text":
        return module.repair_json(source, skip_json_loads=forced, ensure_ascii=False)
    if api == "objects":
        return module.loads(source, skip_json_loads=forced)
    if api == "logs":
        return module.loads(source, skip_json_loads=forced, logging=True)
    raise ValueError(f"unknown API: {api}")


def outcome(call):
    try:
        return {"value": tagged(call())}
    except Exception as error:
        return {"error": type(error).__name__, "message": str(error)}


def witnesses(module):
    rows = {}
    sources = workloads()
    for name in ("valid", "malformed"):
        for index, source in enumerate(sources[name]):
            for api in APIS:
                for forced in (False, True):
                    rows[f"{name}/{index}/{api}/{forced}"] = outcome(
                        lambda api=api, source=source, forced=forced: invoke(module, api, source, forced=forced))
    # Untimed boundary probes stop a fast but content-losing wheel before timing.
    for index, source in enumerate(('[é]', '{界:1}', '[العربية]', '[𐐀]',
                                    '{"x":' + '1' * 128 + '}',
                                    '{"x":true,"y":1,"z":1.0,"n":-0.0}',
                                    '{"x":"\\ud83d\\ude00"}', '{"x":"\ud800"}')):
        for api in APIS:
            rows[f"boundary/{index}/{api}"] = outcome(lambda api=api, source=source: invoke(module, api, source, forced=True))
    for index, source in enumerate(('{"x":1}', '{x: 1}', '{"x":1,"x":2}', '"x":1}', '{"x":1}{"x":2}')):
        for logging in (False, True):
            rows[f"facade/{index}/{logging}"] = outcome(
                lambda source=source, logging=logging: module.repair_json(source, return_objects=True, logging=logging))
        rows[f"strict/{index}"] = outcome(lambda source=source: module.loads(source, strict=True))
    return rows


def witness_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def compare_witnesses(reference, actual, label):
    if not exact_equal(reference, actual):
        mismatches = [key for key in sorted(reference.keys() | actual.keys())
                      if not exact_equal(reference.get(key), actual.get(key))]
        raise ValueError(f"type-sensitive API parity failed for {label}: {', '.join(mismatches[:12])}")


def expected_witness(reference, api, workload):
    by_source = {}
    sources = workloads()
    for name in ("valid", "malformed"):
        for index, source in enumerate(sources[name]):
            row = reference[f"{name}/{index}/{api}/False"]
            if "value" not in row:
                raise ValueError(f"timing workload raised an exception: {name}/{index}/{api}")
            by_source[source] = row["value"]
    return ["list", [by_source[source] for source in sources[workload]]]


def load_backend(backend, root):
    if backend == "installed":
        from importlib.machinery import ExtensionFileLoader
        module = importlib.import_module("pystachy_json_repair")
        if not isinstance(module._native.__spec__.loader, ExtensionFileLoader):
            raise ValueError("installed companion did not load a native extension")
        return module
    path = Path(root).resolve() / ("src" if backend == "upstream" else "ports")
    sys.path.insert(0, str(path))
    module = importlib.import_module("json_repair")
    if Path(module.__file__).resolve().parent != path / "json_repair":
        raise ValueError(f"{backend} imported outside the selected source tree: {module.__file__}")
    return module


def installed_identity(module):
    from importlib.metadata import distribution
    distribution_info = distribution("pystachy-json-repair")
    paths = [Path(module.__file__).resolve(), Path(module._native.__file__).resolve()]
    recorded = {Path(distribution_info.locate_file(item)).resolve()
                for item in distribution_info.files or ()}
    if not all(path in recorded for path in paths):
        raise ValueError("companion modules do not belong to the installed wheel distribution")
    return {"version": distribution_info.version,
            "sha256": {str(path): digest(path) for path in paths},
            "wheel_metadata": distribution_info.read_text("WHEEL"),
            "direct_url": distribution_info.read_text("direct_url.json")}


def check_upstream(root):
    manifest = json.loads((ROOT / "tests/upstream/json_repair/manifest.json").read_text())
    actual_files = {path.relative_to(root).as_posix() for path in (Path(root) / "src").rglob("*.py")}
    expected_files = {filename for filename in manifest["source_sha256"] if filename.endswith(".py")}
    if actual_files != expected_files:
        changed = sorted(actual_files ^ expected_files)
        raise ValueError(f"upstream importable sources differ from {manifest['tag']}: {', '.join(changed[:12])}")
    for filename, expected in manifest["source_sha256"].items():
        path = Path(root) / filename
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"upstream is not pristine {manifest['tag']}: {filename}")
    return {"version": manifest["tag"], "commit": manifest["commit"],
            "source_sha256": manifest["source_sha256"]}


def memory_snapshot():
    if sys.platform == "linux":
        # ru_maxrss can retain the launching parent's high-water mark across
        # exec. Linux's mm counters describe this executable's address space.
        values = {}
        for line in Path("/proc/self/status").read_text().splitlines():
            name, _, value = line.partition(":")
            if name in ("VmRSS", "VmHWM"):
                fields = value.split()
                if name in values or len(fields) != 2 or not fields[0].isdigit() or fields[1] != "kB":
                    raise ValueError(f"invalid /proc/self/status {name} counter")
                values[name] = int(fields[0]) * 1024
        if set(values) != {"VmRSS", "VmHWM"}:
            raise ValueError("/proc/self/status must provide both VmRSS and VmHWM")
        return {"current_rss_bytes": values["VmRSS"], "process_peak_rss_bytes": values["VmHWM"],
                "current_rss_source": "/proc/self/status:VmRSS",
                "process_peak_rss_source": "/proc/self/status:VmHWM",
                "process_peak_rss_scope": "current address space since exec"}
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak *= 1 if sys.platform == "darwin" else 1024
        source = "resource.getrusage(RUSAGE_SELF).ru_maxrss (non-Linux fallback)"
    except ImportError:
        peak = None
        source = None
    return {"current_rss_bytes": None, "process_peak_rss_bytes": peak,
            "current_rss_source": None, "process_peak_rss_source": source,
            "process_peak_rss_scope": "OS high-water; may include inherited pre-exec usage" if source else None}


def call_batch(module, api, sources, group_size, rounds, expected):
    """Bound retention to two workload cycles plus the current group of calls."""
    last = [None] * len(sources)
    checksum = 0
    started = time.perf_counter()
    for _ in range(rounds):
        for start in range(0, len(sources), group_size):
            results = [invoke(module, api, source) for source in sources[start:start + group_size]]
            checksum += sum(len(result) for result in results)
            last[start:start + len(results)] = results
    elapsed = time.perf_counter() - started
    if checksum != rounds * sum(len(result) for result in expected):
        raise ValueError("repeated API result length checksum changed")
    if not exact_equal(tagged(last), tagged(expected)):
        raise ValueError("complete result changed after repeated API calls")
    return elapsed


def calibrate(module, api, sources, group_size, rounds, expected, target):
    """Choose steady-run rounds outside warmups and measured samples."""
    if not math.isfinite(target) or target < 0:
        raise ValueError("min-sample-seconds must be finite and nonnegative")
    limit = max(rounds, CALIBRATION_ROUNDS)
    evidence = {"min_sample_seconds": target, "initial_rounds": rounds,
                "round_limit": limit, "step_limit": CALIBRATION_STEPS,
                "status": "disabled", "samples": []}
    if target == 0:
        return rounds, evidence
    for _ in range(CALIBRATION_STEPS):
        seconds = call_batch(module, api, sources, group_size, rounds, expected)
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("invalid calibration timing")
        evidence["samples"].append({"rounds": rounds, "requests": rounds * len(sources), "seconds": seconds})
        if seconds >= target:
            evidence["status"] = "target_reached"
            break
        if rounds >= limit:
            evidence["status"] = "round_limit"
            break
        if len(evidence["samples"]) == CALIBRATION_STEPS:
            evidence["status"] = "step_limit"
            break
        # At most tenfold growth per probe; zero-resolution clocks cannot cause
        # an unbounded loop. A little headroom reduces warmup-related shortfall.
        growth = min(10.0, target / seconds * 1.1) if seconds else 10.0
        rounds = min(limit, max(rounds + 1, math.ceil(rounds * growth)))
    return rounds, evidence


def worker(args):
    # Workload construction is excluded from both import and first-call timers.
    sources = workloads()
    started = time.perf_counter()
    module = load_backend(args.backend, args.root)
    imported = time.perf_counter() - started
    if args.phase == "parity":
        result = {"witnesses": witnesses(module)}
        if args.backend == "installed":
            result["identity"] = installed_identity(module)
    elif args.phase == "startup":
        started = time.perf_counter()
        value = invoke(module, args.api, sources["malformed"][0])
        elapsed = time.perf_counter() - started
        result = {"import_seconds": imported, "first_request_seconds": elapsed,
                  "witness": tagged(value), **memory_snapshot()}
    else:
        selected = sources[args.workload]
        expected = [invoke(module, args.api, source) for source in selected]
        if args.phase == "steady":
            rounds, calibration = calibrate(module, args.api, selected, args.group_size, args.rounds,
                                            expected, args.min_sample_seconds)
            warmed = [call_batch(module, args.api, selected, args.group_size, rounds, expected)
                      for _ in range(args.warmups)]
            measured = [call_batch(module, args.api, selected, args.group_size, rounds, expected)
                        for _ in range(args.batches)]
            result = {"seconds": measured, "warmup_seconds": warmed,
                      "rounds": rounds, "requests_per_sample": rounds * len(selected), "calibration": calibration,
                      "witness": tagged(expected), **memory_snapshot()}
        else:
            import gc
            # Python GC does not collect the native heap. Both allocator retention
            # and native GC behavior contribute to RSS; this is not a leak proof.
            call_batch(module, args.api, selected, args.group_size, args.rounds, expected)
            gc.collect()
            samples = [{"requests_after_warmup": 0, **memory_snapshot()}]
            for block in range(args.batches):
                call_batch(module, args.api, selected, args.group_size, args.rounds, expected)
                gc.collect()
                samples.append({"requests_after_warmup": (block + 1) * args.rounds * len(selected),
                                **memory_snapshot()})
            result = {"memory_samples": samples, "witness": tagged(expected)}
    print(json.dumps(result, ensure_ascii=True))


def run_child(command, timeout):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME")}
    started = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
    elapsed = time.perf_counter() - started
    if process.returncode:
        raise RuntimeError(f"API benchmark child failed ({process.returncode}): {command}\n{process.stderr}")
    result = json.loads(process.stdout)
    result.update({"process_wall_seconds": elapsed, "command": command, "stderr": process.stderr})
    return result


def validate_samples(sample, batches, warmups):
    for field, count in (("seconds", batches), ("warmup_seconds", warmups)):
        values = sample.get(field)
        if not isinstance(values, list) or len(values) != count or any(
                type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
            raise ValueError(f"invalid or missing {field}")


def campaign(args):
    upstream = check_upstream(args.upstream)
    source_before = source_identity(args.adapted)
    harness_sha = {str(path): digest(path) for path in HARNESS_PATHS}
    python_sha = digest(sys.executable)
    roots = {"upstream": str(args.upstream.resolve()), "adapted": str(args.adapted.resolve()), "installed": ""}

    def run(backend, phase, *extra):
        command = [sys.executable, "-I", str(Path(__file__).resolve()), "--worker",
                   "--backend", backend, "--root", roots[backend], "--phase", phase, *extra]
        return run_child(command, args.timeout)

    parity = {backend: run(backend, "parity") for backend in BACKENDS}
    reference = parity["upstream"]["witnesses"]
    for backend in BACKENDS[1:]:
        compare_witnesses(reference, parity[backend]["witnesses"], backend)
    report = {
        "schema": 1, "platform": platform.platform(), "python": sys.version,
        "python_executable": sys.executable, "python_sha256": python_sha, "harness_sha256": harness_sha,
        "cpu": args.cpu,
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), platform.processor()) if Path("/proc/cpuinfo").exists() else platform.processor(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "upstream": upstream, "adapted_source": source_before,
        "installed": parity["installed"]["identity"],
        "input_sha256": hashlib.sha256(json.dumps(workloads(), ensure_ascii=True).encode()).hexdigest(),
        "scopes": {
            "parity": "complete tagged outputs/errors across all backends before any timing",
            "steady": "ordinary public API calls, result-list/loop overhead and length checksum; includes boundary conversion; excludes calibration, startup, input construction and complete validation",
            "calibration": "steady workers increase initial rounds toward min_sample_seconds before warmups; up to eight checked probes and max(initial_rounds, 1000000) rounds; calibration is excluded from measured samples; the target is not a timing gate",
            "startup": "fresh isolated Python worker launch to exit, including shared harness setup and reporting; backend import and first malformed call also timed separately",
            "memory": "separate fresh process per API; Linux /proc/self/status VmRSS and VmHWM since exec after warmup and sustained ordinary calls; non-Linux rusage fallback is labeled and may include inherited pre-exec high-water; CPython gc.collect before sampling; native GC is not forced",
            "group_size": "maximum calls grouped in a Python loop, capped by workload size; not a native batch API",
            "inputs": "constructed trace-like records; mixed is 80% valid/20% malformed by request count, not a measured production distribution",
        },
        "options": {key: getattr(args, key) for key in ("pairs", "batches", "warmups", "rounds", "group_sizes", "memory_rounds", "min_sample_seconds")},
        "parity": {
            "reference_witnesses": reference,
            "checks": {backend: {"matched": len(reference), "witness_sha256": witness_digest(row["witnesses"]),
                                  "command": row["command"], "process_wall_seconds": row["process_wall_seconds"]}
                       for backend, row in parity.items()},
        }, "samples": [], "summary": {},
    }
    if not args.check_only:
        for pair in range(args.pairs):
            order = BACKENDS[pair % 3:] + BACKENDS[:pair % 3]
            for api in APIS:
                for backend in order:
                    sample = run(backend, "startup", "--api", api)
                    expected = reference[f"malformed/0/{api}/False"]["value"]
                    if not exact_equal(sample["witness"], expected):
                        raise ValueError(f"first request changed: {backend}/{api}")
                    sample["witness_sha256"] = witness_digest(sample.pop("witness"))
                    report["samples"].append({"pair": pair, "phase": "startup", "backend": backend, "api": api, **sample})
                for workload in workloads():
                    for group in args.group_sizes:
                        for backend in order:
                            sample = run(backend, "steady", "--api", api, "--workload", workload,
                                         "--group-size", str(group), "--rounds", str(args.rounds),
                                         "--batches", str(args.batches), "--warmups", str(args.warmups),
                                         "--min-sample-seconds", str(args.min_sample_seconds))
                            validate_samples(sample, args.batches, args.warmups)
                            if not exact_equal(sample["witness"], expected_witness(reference, api, workload)):
                                raise ValueError(f"timing worker output changed: {backend}/{api}/{workload}")
                            sample["witness_sha256"] = witness_digest(sample.pop("witness"))
                            row = {"pair": pair, "phase": "steady", "backend": backend, "api": api,
                                   "workload": workload, "group_size": group, **sample}
                            report["samples"].append(row)
                print(f"{pair + 1}/{args.pairs} {api}: checked API measurements collected", flush=True)
        # Memory profiling is deliberately outside the ordinary timing campaign.
        for api in APIS:
            for backend in BACKENDS:
                sample = run(backend, "memory", "--api", api, "--workload", "mixed", "--group-size", "32",
                             "--rounds", str(args.memory_rounds), "--batches", str(args.batches))
                if not exact_equal(sample["witness"], expected_witness(reference, api, "mixed")):
                    raise ValueError(f"memory worker output changed: {backend}/{api}")
                sample["witness_sha256"] = witness_digest(sample.pop("witness"))
                report["samples"].append({"phase": "memory", "backend": backend, "api": api, **sample})
        groups = {}
        for row in report["samples"]:
            if row["phase"] == "steady":
                key = f"{row['api']}/{row['workload']}/group-{row['group_size']}/{row['backend']}"
                groups.setdefault(key, []).append(statistics.median(row["seconds"]) / row["requests_per_sample"])
        report["summary"] = {key: {"median_seconds_per_request": statistics.median(values),
                                   "process_medians_seconds_per_request": values}
                             for key, values in groups.items()}
    if source_before != source_identity(args.adapted) or check_upstream(args.upstream) != upstream:
        raise ValueError("source changed during API campaign")
    after = run("installed", "parity")
    if after["identity"] != report["installed"] or {str(path): digest(path) for path in HARNESS_PATHS} != harness_sha or digest(sys.executable) != python_sha:
        raise ValueError("installed wheel, Python or harness changed during API campaign")
    compare_witnesses(reference, after["witnesses"], "installed after campaign")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=BACKENDS, help=argparse.SUPPRESS)
    parser.add_argument("--root", help=argparse.SUPPRESS)
    parser.add_argument("--phase", choices=("parity", "startup", "steady", "memory"), help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, default="text", help=argparse.SUPPRESS)
    parser.add_argument("--workload", choices=tuple(workloads()), default="mixed", help=argparse.SUPPRESS)
    parser.add_argument("--group-size", type=int, default=1, help=argparse.SUPPRESS)
    parser.add_argument("--upstream", type=Path, help="pristine pinned json_repair checkout")
    parser.add_argument("--adapted", type=Path, default=ROOT, help="Pystachy checkout supplying ports/json_repair")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--min-sample-seconds", type=float, default=0.2,
                        help="calibrate steady sample duration toward this target; 0 disables calibration")
    parser.add_argument("--group-sizes", type=int, nargs="+", default=[1, 32])
    parser.add_argument("--memory-rounds", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--check-only", action="store_true", help="validate installed/native provenance and exact API parity without timings")
    args = parser.parse_args()
    if min(args.pairs, args.batches, args.rounds, args.memory_rounds, args.group_size, *args.group_sizes) < 1 or args.warmups < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("counts and timeout must be positive; warmups must be nonnegative")
    if not math.isfinite(args.min_sample_seconds) or args.min_sample_seconds < 0:
        parser.error("min-sample-seconds must be finite and nonnegative")
    if args.worker:
        if not args.backend or not args.phase or args.root is None:
            parser.error("worker requires backend, phase and root")
        worker(args)
        return
    if args.upstream is None or args.output is None or args.cpu is None:
        parser.error("--upstream, --output and --cpu are required")
    affinity = os.sched_getaffinity(0)
    if args.cpu not in affinity:
        parser.error("cpu is outside available affinity mask")
    try:
        os.sched_setaffinity(0, {args.cpu})
        report = campaign(args)
    finally:
        os.sched_setaffinity(0, affinity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    print(f"API parity passed; evidence: {args.output}")


if __name__ == "__main__":
    main()
