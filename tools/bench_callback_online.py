"""Measure online callable specialization with unchanged stdlib bisect bodies."""
import argparse
import ast
from bisect import bisect_left
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import statistics
import sys

from bench_stream_online import (
    execute, paired_ratios, parse_online_stats, summarize,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/fixtures/callback_skew.py"
PHASES = ("cold", "warm", "shift", "recovery")


def write_inputs(directory):
    original = SOURCE.read_text()
    tree = ast.parse(original)
    search_before = ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "search"))
    # Only entry dispatch differs. Both concrete calls use the original search
    # and stdlib bisect bodies; the closure control retains generic dispatch.
    replacement = ast.parse("""
def dispatch(index: int) -> int:
    if index == 0:
        return search(text_length)
    if index == 1:
        return search(alias_length)
    return call_search(callbacks[index])
""").body[0]
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch":
            tree.body[i] = replacement
    search_after = ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "search"))
    if search_before != search_after:
        raise RuntimeError("Concrete input changed the search body")
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, source in [("generic", original), ("concrete", ast.unparse(tree) + "\n")]:
        target = directory / f"callback_{name}.py"
        target.write_text(source)
        result[name] = {"path": str(target), "text": source,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    return result


def selected_index(phase, i, count):
    if phase == "cold":
        return int(i == count - 1)
    if phase == "shift":
        if i < count // 2:
            return i % 3
        return 0 if i == count - 1 else 1 + i % 2
    return 0


def expected_results(counts):
    # Independent CPython bisect oracle for the three sorted field projections.
    queries = [(i * 569) % 1025 for i in range(509)]
    sums = [sum(bisect_left([i + offset for i in range(1024)], q) for q in queries)
            for offset in (0, 11, 5)]
    expected = {}
    fallback = 0
    for phase, count in counts.items():
        choices = [selected_index(phase, i, count) for i in range(count)]
        expected[phase] = sum(sums[index] for index in choices)
        fallback += sum(index != 0 for index in choices)
    return expected, fallback


def parse_phases(output, counts, expected):
    phases = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 6 or fields[0] != "phase":
            raise RuntimeError(f"Unexpected output: {line!r}")
        _, phase, calls, checksum, wall, cpu = fields
        if phase not in counts or phase in phases or int(calls) != counts[phase] or int(checksum) != expected[phase]:
            raise RuntimeError(f"Incorrect phase result: {line!r}")
        phases[phase] = {"calls": int(calls), "checksum": int(checksum),
                         "wall_seconds": float(wall), "self_cpu_seconds": float(cpu)}
    if set(phases) != set(counts):
        raise RuntimeError("Missing phase results")
    return phases


def callable_assembly(assembly):
    """Extract compiler application bodies, ignoring ELF startup/PLT stubs."""
    bodies = {}
    name = ""
    for line in assembly.splitlines():
        match = re.match(r"^[0-9a-f]+ <([^>]+)>:$", line)
        if match:
            name = match[1]
            if name == "main" or name == "pystachy_online_entry" or name.startswith(("f.search", "f.call_search", "f.dispatch", "f.phase_batch")):
                bodies[name] = []
        elif name in bodies:
            bodies[name].append(line)
    return {name: "\n".join(lines) for name, lines in bodies.items()}


def inspect_image(name, target, source, options, env, build):
    """Keep one untimed installed image to establish changed native hot code."""
    stats = build / f"{name}-image.tsv"
    before = set(Path("/tmp").glob("pystachy-online-*"))
    record = execute([str(target), "check"], dict(env, **options,
                     PYSTACHY_ONLINE_STATS=str(stats), PYSTACHY_ONLINE_KEEP="1"))
    record["online_stats"] = parse_online_stats(stats, 2036, 1018)
    directories = []
    for directory in set(Path("/tmp").glob("pystachy-online-*")) - before:
        manifest = directory / "expected"
        if manifest.is_file() and f"source\t{source}\t" in manifest.read_text():
            directories.append(directory)
    if len(directories) != 1:
        raise RuntimeError("Could not identify the one retained callback image")
    directory = directories[0]
    try:
        artifact = build / f"{name}-image.so"
        shutil.copy2(directory / "trace.so", artifact)
        assembly = execute(["objdump", "-d", str(artifact)], env)["stdout"]
        bodies = callable_assembly(assembly)
        if "pystachy_online_entry" not in bodies:
            raise RuntimeError("Loaded image entry is absent from native disassembly")
        indirect = [line for body in bodies.values() for line in body.splitlines()
                    if re.search(r"\bcall\w*\s+\*", line)]
        if indirect:
            raise RuntimeError(f"Loaded callback search still contains indirect calls: {indirect}")
        exports = execute(["nm", "-D", "--defined-only", str(artifact)], env)["stdout"]
        if {line.split()[-1] for line in exports.splitlines()} != {
                "pystachy_online_entry", "pystachy_online_abi", "pystachy_online_selection"}:
            raise RuntimeError("Loaded image exposes unexpected runtime definitions")
        record.update(image_path=str(artifact), image_bytes=artifact.stat().st_size,
                      image_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                      application_assembly=bodies, application_indirect_calls=indirect,
                      dynamic_exports=exports,
                      dynamic_imports=execute(["nm", "-D", "--undefined-only", str(artifact)], env)["stdout"],
                      compiler_log=(directory / "compiler.log").read_text(),
                      note="Untimed check; native application bodies have no indirect callback call. This is code evidence, not a time attribution.")
    finally:
        shutil.rmtree(directory)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, "-m", "pystachy"]))
    parser.add_argument("--online-compiler", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--jit-samples", type=int, default=3)
    parser.add_argument("--cold", type=int, default=200)
    parser.add_argument("--warm", type=int, default=50000)
    parser.add_argument("--shift", type=int, default=40)
    parser.add_argument("--recovery", type=int, default=50000)
    parser.add_argument("--timing-cpu", type=int)
    parser.add_argument("--skip-inline", action="store_true", help="omit the optional inline-runtime online tier")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmarks/callback-online.json")
    args = parser.parse_args()
    if args.samples < 3 or args.jit_samples < 1 or args.cold < 101 or min(args.warm, args.shift, args.recovery) < 1:
        parser.error("at least three samples, one JIT sample, cold > 100, and positive phase counts are required")
    native = args.online_compiler.resolve()
    if not native.is_file() or not os.access(native, os.X_OK):
        parser.error("--online-compiler must be a native executable")
    compiler = shlex.split(args.compiler)
    build = ROOT / "build/callback-online"
    inputs = write_inputs(build / "source")
    counts = {name: getattr(args, name) for name in PHASES}
    expected, fallback = expected_results(counts)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("PYSTACHY_ONLINE") or key.startswith("PYSTACHY_FEEDBACK") or key in (
                "PYSTACHY_SKEW_PROFILE", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
                "PYSTACHY_IRFX", "PYSTACHY_SUMMARY_STATS"):
            env.pop(key)
    env["PYSTACHY_FEEDBACK_FUNCTION"] = "search"
    online_options = {"PYSTACHY_ONLINE": "1", "PYSTACHY_ONLINE_COMPILER": str(native)}
    variants = [("aot_generic", "generic", {}), ("online_imports", "generic", online_options)]
    if not args.skip_inline:
        variants.append(("online_inline", "generic", dict(online_options, PYSTACHY_ONLINE_INLINE_RUNTIME="1")))
    variants.append(("aot_concrete", "concrete", {}))
    files = [SOURCE, Path(__file__).resolve(), ROOT / "tools/bench_stream_online.py",
             ROOT / "lib/bisect.py", ROOT / "runtime.c", ROOT / "runtime.py"]
    files.extend(sorted((ROOT / "src/pystachy_compiler").glob("*.py")))
    files.extend(Path(row["path"]) for row in inputs.values())

    def hashes():
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}

    before = hashes()
    binary_hash = hashlib.sha256(native.read_bytes()).hexdigest()
    affinity = os.sched_getaffinity(0)
    cpu = min(affinity) if args.timing_cpu is None else args.timing_cpu
    if cpu not in affinity:
        parser.error("--timing-cpu is outside the allowed affinity set")
    info = {"schema": "pystachy-callback-online-v1", "status": "incomplete",
            "platform": platform.platform(), "machine": platform.machine(), "python": sys.version, "compiler": compiler,
            "online_compiler": str(native), "online_compiler_sha256": binary_hash,
            "git_head": execute(["git", "rev-parse", "HEAD"], env)["stdout"],
            "git_status": execute(["git", "status", "--short"], env)["stdout"],
            "inputs": inputs, "counts": counts, "expected_checksums": expected,
            "fallback_calls": fallback, "samples": args.samples, "jit_samples": args.jit_samples,
            "timing_affinity_cpu": cpu, "allowed_affinity": sorted(affinity),
            "workload": "509 length queries over 1024 text records per call; unchanged stdlib bisect_left key loop",
            "dynamic_information": "Exact top-level callback identity within one Callable[[Record], int] signature",
            "distribution": "Controlled primary skew followed by named-secondary and closure misses, then recovery",
            "timers": {"whole_process": "wall includes startup and compilation; CPU includes waited descendants",
                       "phase": "wall includes online compilation; process_time excludes compiler child CPU"},
            "builds": {}, "checks": {}, "samples_raw": {}}
    llvm = env.get("PYSTACHY_LLVM", "")
    if llvm:
        info["llvm"] = execute([str(Path(llvm) / "clang"), "--version"], env)["stdout"].splitlines()[0]
    try:
        oracle = execute([sys.executable, str(SOURCE), "check"], env)["stdout"]
        info["checks"]["upstream_cpython"] = oracle
        for name, source, options in variants:
            target = build / name
            record = execute([*compiler, "build", inputs[source]["path"], "-o", str(target)], dict(env, **options))
            record.update(executable_bytes=target.stat().st_size,
                          executable_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), options=options)
            info["builds"][name] = record
            check_env = dict(env, **options)
            stats = build / f"check-{name}.tsv"
            check_env["PYSTACHY_ONLINE_STATS"] = str(stats)
            check = execute([str(target), "check"], check_env)
            if check["stdout"] != oracle:
                raise RuntimeError(f"{name} exact positions differ from CPython")
            if name.startswith("online_"):
                check["online_stats"] = parse_online_stats(stats, 2036, 1018)
            info["checks"][name] = check

        info["loaded_image_checks"] = {
            name: inspect_image(name, build / name, inputs[source]["path"], options, env, build)
            for name, source, options in variants if name.startswith("online_")}
        generic_assembly = callable_assembly(execute(["objdump", "-d", str(build / "aot_generic")], env)["stdout"])
        generic_indirect = [line for body in generic_assembly.values() for line in body.splitlines()
                            if re.search(r"\bcall\w*\s+\*", line)]
        if not generic_indirect:
            raise RuntimeError("Generic baseline has no unresolved application callback call")
        info["generic_indirect_call_sites"] = generic_indirect
        info["concrete_aot_assembly"] = callable_assembly(
            execute(["objdump", "-d", str(build / "aot_concrete")], env)["stdout"])
        info["concrete_loop_note"] = "Inspect f.phase_batch's per-repetition dispatch call and f.dispatch's query/search backedges; repeated searches remain inside the timed loop."
        ir_path = build / "online.ll"
        execute([*compiler, "ir", inputs["generic"]["path"], "-o", str(ir_path)], dict(env, **online_options))
        host_ir = ir_path.read_text()
        definitions = re.findall(r"^define .*@f\.search[^\n]*", host_ir, re.MULTILINE)
        if len(definitions) != 1 or "@pys_online_callable(" not in host_ir:
            raise RuntimeError("Online host must contain one generic search and a runtime callable observer")
        info["host_ir_check"] = {"search_definitions": definitions,
                                 "sha256": hashlib.sha256(ir_path.read_bytes()).hexdigest()}
        info["jit_cache_preparation"] = execute([*compiler, "run", inputs["generic"]["path"], "check"], env)
        if info["jit_cache_preparation"]["stdout"] != oracle:
            raise RuntimeError("Ordinary JIT exact-position validation differs")

        def measure(name, command, options, sample):
            stats = build / f"{name}-{sample}.tsv"
            stats.unlink(missing_ok=True)
            options = dict(env, **options, PYSTACHY_ONLINE_STATS=str(stats))
            record = execute([*command, "phases", *[str(counts[p]) for p in PHASES]], options)
            record["phases"] = parse_phases(record["stdout"], counts, expected)
            if name.startswith("online_"):
                record["online_stats"] = parse_online_stats(stats, sum(counts.values()), fallback)
            info["samples_raw"].setdefault(name, []).append(record)

        os.sched_setaffinity(0, {cpu})
        try:
            for sample in range(args.samples):
                offset = sample % len(variants)
                for name, _, options in variants[offset:] + variants[:offset]:
                    measure(name, [str(build / name)], options, sample)
            jit = [("jit_generic", "generic"), ("jit_concrete", "concrete")]
            for sample in range(args.jit_samples):
                for name, source in (jit if sample % 2 == 0 else list(reversed(jit))):
                    measure(name, [*compiler, "run", inputs[source]["path"]], {}, sample)
        finally:
            os.sched_setaffinity(0, affinity)
        info["summary"] = summarize(info["samples_raw"])
        info["paired_ratios"] = {
            "aot_generic_over_" + name: paired_ratios(info["samples_raw"], "aot_generic", name)
            for name, _, _ in variants if name != "aot_generic"}
        info["paired_ratios"]["jit_generic_over_concrete"] = paired_ratios(info["samples_raw"], "jit_generic", "jit_concrete")
        info["estimated_break_even_calls"] = {}
        for name in (name for name, _, _ in variants if name.startswith("online_")):
            records = info["samples_raw"][name]
            saving = statistics.median([
                (base["phases"]["warm"]["wall_seconds"] - row["phases"]["warm"]["wall_seconds"]) / args.warm
                for base, row in zip(info["samples_raw"]["aot_generic"], records)])
            cost = statistics.median([row["online_stats"]["site"]["compile_wall_s"] + row["online_stats"]["site"]["load_wall_s"] for row in records])
            info["estimated_break_even_calls"][name] = {"steady_saving_seconds_per_call": saving,
                "compile_and_load_seconds": cost, "calls": cost / saving if saving > 0 else None,
                "assumption": "Stationary primary-only distribution and measured warm per-call saving; excludes 99 warmup calls"}
        if hashes() != before or hashlib.sha256(native.read_bytes()).hexdigest() != binary_hash:
            raise RuntimeError("Source or compiler changed during measurement; rerun")
        info["status"] = "complete"
    except Exception as error:
        info["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        info["source_sha256_before"] = before
        info["source_sha256_after"] = hashes()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "status": info["status"],
                      "estimated_break_even_calls": info["estimated_break_even_calls"]}, indent=2))


if __name__ == "__main__":
    main()
