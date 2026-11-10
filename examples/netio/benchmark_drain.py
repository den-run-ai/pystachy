"""Compare two pipe consumers on identical replayed compiler and binary output.

Timings include child startup, pipe I/O, collection and hex encoding, but exclude
compiler work and AOT builds. Copy-volume models are separate from wall time.
"""

import argparse
import ast
import contextlib
import hashlib
import io
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import types
from unittest import mock

import check
import compiler_dogfood as dogfood


# The writer and its input are identical for both consumers. Blocking writes can
# be partial; collect() owns both child groups and applies the overall deadline.
WRITER = """import os,sys
with open(sys.argv[1], 'rb') as stream:
    data = stream.read()
at = 0
while at < len(data):
    count = os.write(1, data[at:at + 65536])
    if count <= 0:
        raise RuntimeError('writer made no progress')
    at += count
"""


def copy_volume(source, total, fragment):
    """Model native concat/join byte copies using sized objects, without timing.

    Execute the supplied drain with deterministic read sizes. Replace bytes
    literals with a sized proxy: native bytes addition and join each copy their
    complete result. Initial reads, metadata, GC and hex encoding are excluded.
    The real pipe runs separately validate every actual output byte.
    """
    counters = {"payload_copy_bytes": 0, "copy_operations": 0, "reads": 0}
    remaining = total

    class ByteShape:
        def __init__(self, size):
            self.size = size

        def __len__(self):
            return self.size

        def copied(self, size):
            counters["payload_copy_bytes"] += size
            counters["copy_operations"] += 1
            return ByteShape(size)

        def __add__(self, other):
            return self.copied(self.size + len(other))

        def join(self, values):
            return self.copied(sum(map(len, values)) + self.size * max(0, len(values) - 1))

        def hex(self):
            return str(self.size)

    class Literals(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, bytes):
                return ast.copy_location(ast.Call(func=ast.Name(id="_ByteShape", ctx=ast.Load()),
                                                  args=[ast.Constant(len(node.value))], keywords=[]), node)
            return node

    key = types.SimpleNamespace(fd=64, data=0)
    selector = mock.MagicMock()
    selector.__enter__.return_value = selector
    selector.select.return_value = [(key, 1)]

    def read(fd, maximum):
        nonlocal remaining
        if fd != 64 or maximum < 1:
            raise ValueError("unexpected read in copy-volume model")
        size = min(remaining, maximum, fragment)
        remaining -= size
        counters["reads"] += 1
        return ByteShape(size)

    close = mock.Mock()
    oracle = types.SimpleNamespace(DefaultSelector=lambda: selector, EVENT_READ=1,
                                   close_fd=close, read=read, set_blocking=lambda fd, flag: None)
    code = compile(ast.fix_missing_locations(Literals().visit(ast.parse(source))), "<copy-volume>", "exec")
    namespace = {"__name__": "copy_volume", "_ByteShape": ByteShape}
    output = io.StringIO()
    with mock.patch.dict(sys.modules, {"netio": oracle}), contextlib.redirect_stdout(output):
        exec(code, namespace)
        namespace["drain"]([64], 30.0, total)
    if remaining or output.getvalue() != f"done 0 {total}\n" or close.call_args_list != [mock.call(64)]:
        raise ValueError("copy-volume model did not complete the bounded stream")
    return counters


def summarize(rows):
    values = [row["end_to_end_s"] for row in rows]
    median = statistics.median(values)
    return {"median_s": median, "min_s": min(values), "max_s": max(values),
            "mad_s": statistics.median(abs(value - median) for value in values)}


def verify(args, report):
    pinned = (check.ROOT / ".python-version").read_text().strip()
    if sys.implementation.name != "cpython" or platform.python_version() != pinned:
        raise RuntimeError(f"use pinned CPython {pinned}; running {platform.python_version()}")
    if args.cpu is not None:
        if not hasattr(os, "sched_getaffinity") or args.cpu not in os.sched_getaffinity(0):
            raise ValueError("--cpu must be in the process affinity mask")
        os.sched_setaffinity(0, {args.cpu})
    compiler = check.compiler_command(args.compiler)
    before = args.before.read_bytes()
    after = (check.HERE / "drain.py").read_bytes()
    source_hashes = dogfood.sources() | {"examples/netio/benchmark_drain.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if source_hashes.get("examples/netio/drain.py") != hashlib.sha256(after).hexdigest():
        raise RuntimeError("consumer snapshot differs from source inventory")
    artifacts = dogfood.artifacts(compiler + [sys.executable])
    report.update(python=pinned, platform=platform.platform(), compiler=compiler,
                  compiler_artifacts_sha256=artifacts, source_sha256=source_hashes,
                  before_path=str(args.before.resolve()), before_sha256=hashlib.sha256(before).hexdigest(),
                  after_sha256=hashlib.sha256(after).hexdigest(), samples=args.samples, warmups=args.warmups,
                  cpu=args.cpu, affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                  load_before=os.getloadavg(), runs={}, warmup_runs=[], execution_order=[],
                  timing_scope="End-to-end replay: writer and consumer startup, pipe reads, buffering, hex output and parent capture/parsing. "
                               "Compiler work, AOT builds, expected-payload comparisons, final worker cleanup and copy-volume models are excluded.")
    report["copy_volume"] = {
        "scope": "Deterministic native concat/join payload-copy model using sized byte proxies, not measured allocations or instructions. "
                 "Initial read copies and hex encoding are excluded.",
        "cases": {},
    }
    for total, fragment in ((4096, 1), (8388608, 8192)):
        report["copy_volume"]["cases"][f"{total}_bytes_in_{fragment}_byte_fragments"] = {
            name: copy_volume(source, total, fragment) for name, source in (("before", before), ("after", after))}
    with tempfile.TemporaryDirectory(prefix="pystachy-netio-drain-bench-") as temporary:
        directory = Path(temporary)
        env = check.environment(directory)
        cc = check.c_compiler(args.cc, env)
        version = dogfood.run("bridge/version", cc + ["--version"], env, directory, timeout=args.timeout)
        report["bridge_compiler"] = {"command": cc, "version": version.stdout.decode(errors="replace").splitlines()[0]}
        report["llvm_bin"] = env.get("PYSTACHY_LLVM", "compiler default")
        bridge = check.build_bridge(directory, env, cc, args.timeout, runner=dogfood.run)
        report["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
        ir_command = [sys.executable, str(check.ROOT / "pystachy.py"), "rt",
                      str(check.ROOT / "runtime.py")]
        reference, _ = dogfood.serial(ir_command, env, directory, args.timeout, dogfood.MAXIMUM)
        if reference.returncode or not reference.stdout or reference.stderr:
            raise ValueError("independent compiler IR capture failed: " + repr(dogfood.witness(reference)))
        report["compiler_ir"] = dogfood.witness(reference) | {"command": ir_command}
        payloads = {"small_64": bytes(range(64)), "compiler_ir": reference.stdout,
                    "binary_8m": bytes(range(256)) * 32768}
        report["payloads"] = {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                              for name, data in payloads.items()}
        variants = []
        for version, source in (("before", before), ("after", after)):
            path = directory / f"drain_{version}.py"
            path.write_bytes(source)
            variants.append((f"cpython_{version}", [sys.executable, str(path)], check.environment(directory, oracle=True)))
            if not args.cpython_only:
                executable = directory / f"drain_{version}"
                check.quiet(version + "/build", dogfood.run(version + "/build", compiler + ["build", str(path), "-o", str(executable)],
                                                            env, check.ROOT, timeout=args.timeout))
                if not executable.is_file() or not os.access(executable, os.X_OK):
                    raise ValueError("compiler did not create a fresh consumer executable")
                report[f"aot_{version}_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
                variants.append((f"aot_{version}", [str(executable)], env))
        for case, payload in payloads.items():
            path = directory / f"{case}.bin"
            path.write_bytes(payload)
            command = [sys.executable, "-c", WRITER, str(path)]
            expected = subprocess.CompletedProcess(command, 0, payload, b"")
            report["runs"][case] = {mode: [] for mode, _, _ in variants}
            for sample in range(-args.warmups, args.samples):
                offset = (sample + args.warmups) % len(variants)
                for mode, consumer, consumer_env in variants[offset:] + variants[:offset]:
                    actual, timings = dogfood.collect([command], consumer, env, consumer_env, directory, args.timeout, len(payload))
                    dogfood.compare(case + "/" + mode, actual[0], expected)
                    row = timings | {"sample": sample, "mode": mode, "case": case}
                    if sample < 0:
                        report["warmup_runs"].append(row)
                    else:
                        report["runs"][case][mode].append(row)
                        report["execution_order"].append({"case": case, "sample": sample, "mode": mode})
                        print(f"{case}/{mode}: {timings['end_to_end_s']:.6f}s; exact bytes verified", flush=True)
                    check.write_report(args.json, report)
        report["summary"] = {case: {mode: summarize(rows) for mode, rows in modes.items()}
                             for case, modes in report["runs"].items()}
    current = dogfood.sources() | {"examples/netio/benchmark_drain.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if (current != source_hashes or dogfood.artifacts(compiler + [sys.executable]) != artifacts
            or args.before.read_bytes() != before or (check.HERE / "drain.py").read_bytes() != after):
        raise RuntimeError("consumed sources or executables changed; rerun on the final tree")
    if any(len(rows) != args.samples for modes in report["runs"].values() for rows in modes.values()):
        raise RuntimeError("missing drain benchmark samples")
    report.update(result="pass", load_after=os.getloadavg())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path, help="baseline drain.py saved from the comparison revision")
    parser.add_argument("--compiler", default=str(check.ROOT / "pystachy"))
    parser.add_argument("--cc")
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.samples < 1 or args.warmups < 0 or args.timeout <= 0 or not math.isfinite(args.timeout):
        parser.error("positive samples, nonnegative warmups and a finite positive timeout are required")
    affinity = os.sched_getaffinity(0) if hasattr(os, "sched_getaffinity") else None
    report = {"schema": 1, "result": "running", "scenario": "drain_replay_before_after"}
    check.write_report(args.json, report)
    try:
        verify(args, report)
    except Exception as error:
        report.update(result="fail", error=str(error))
        check.write_report(args.json, report)
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if affinity is not None:
            os.sched_setaffinity(0, affinity)
    check.write_report(args.json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
