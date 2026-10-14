"""Measure cold online native compilation, warm dispatch, and stream-mix shifts.

The online host is an AOT executable. It compiles and loads its specialization
inside each measured process. Ordinary pre-execution JIT controls are reported
separately. No persistent online artifact cache is used.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shlex
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/stream_skew.py"
CHECKSUM = 586964006
ORACLE = (
    "from pathlib import Path; import sys; "
    "p=Path(sys.argv[1]); sys.argv=sys.argv[1:]; "
    "code=p.read_text().replace('_stream=stream', 'instream=stream'); "
    "exec(compile(code,str(p),'exec'))"
)


def execute(command, env, timeout=600):
    """Measure one waited child and its waited descendants, without overlap."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=timeout)
    wall = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    user = after.ru_utime - before.ru_utime
    system = after.ru_stime - before.ru_stime
    record = {"command": list(map(str, command)), "wall_seconds": wall,
              "inclusive_user_cpu_seconds": user,
              "inclusive_system_cpu_seconds": system,
              "inclusive_cpu_seconds": user + system,
              "stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
              "returncode": result.returncode}
    if result.returncode:
        raise RuntimeError(f"{shlex.join(map(str, command))}\n{result.stdout}{result.stderr}")
    return record


def parse_phases(output, counts):
    lines = output.splitlines()
    if not lines or lines[0] != f"tokens 544 {CHECKSUM}":
        raise RuntimeError(f"Missing exact-token validation: {output!r}")
    phases = {}
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 6 or fields[0] != "phase":
            raise RuntimeError(f"Unexpected phase output: {line!r}")
        _, name, calls, checksum, wall, cpu = fields
        if name not in counts or name in phases or int(calls) != counts[name]:
            raise RuntimeError(f"Unexpected phase/call count: {line!r}")
        if int(checksum) != CHECKSUM * counts[name]:
            raise RuntimeError(f"Phase checksum differs: {line!r}")
        phases[name] = {"calls": int(calls), "checksum": int(checksum),
                        "wall_seconds": float(wall), "self_cpu_seconds": float(cpu)}
    if set(phases) != set(counts):
        raise RuntimeError(f"Missing phase: {output!r}")
    return phases


def parse_online_stats(path, calls, file_calls):
    raw = path.read_text()
    lines = raw.splitlines()
    required = {"site", "calls", "attempts", "installs", "hits", "misses",
                "trigger_call", "compile_wall_s", "compile_cpu_s", "load_wall_s",
                "failure", "compiler_pid"}
    if len(lines) != 3 or lines[0] != "pystachy-online-v1":
        raise RuntimeError(f"Expected one online site in {path}: {raw!r}")
    names = lines[1].split("\t")
    values = lines[2].split("\t")
    if set(names) != required or len(values) != len(names):
        raise RuntimeError(f"Unexpected online statistics schema: {raw!r}")
    row = dict(zip(names, values))
    for field in ("calls", "attempts", "installs", "hits", "misses", "trigger_call", "compiler_pid"):
        row[field] = int(row[field])
    for field in ("compile_wall_s", "compile_cpu_s", "load_wall_s"):
        row[field] = float(row[field])
    if row["calls"] != calls or row["attempts"] != 1 or row["installs"] != 1:
        raise RuntimeError(f"Online compilation was not exercised once: {row}")
    if row["failure"] != "none" or row["trigger_call"] != 100 or row["compiler_pid"] <= 0:
        raise RuntimeError(f"Online compilation failed or triggered unexpectedly: {row}")
    if row["compile_wall_s"] <= 0 or row["compile_cpu_s"] <= 0 or row["load_wall_s"] < 0:
        raise RuntimeError(f"Online compile/load timing is invalid: {row}")
    # Calls1..99 warm up; call100 compiles and immediately uses the image.
    # Every file appears after this threshold and must take generic fallback.
    expected_misses = 99 + file_calls
    if row["misses"] != expected_misses or row["hits"] != calls - expected_misses:
        raise RuntimeError(f"Online hot path or changed-mix fallback counts differ: {row}")
    return {"raw": raw, "site": row}


def distribution(values):
    return {"values": values, "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def write_inputs(directory):
    """Keep concrete controls out of the generic and online host's native image.

    Only benchmark call plumbing changes. The tokenizer AST and imported shlex
    parser stay identical; the concrete control is a byte-exact source copy.
    """
    original = SOURCE.read_text()
    tree = ast.parse(original)
    tokenizer = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "tokenize")
    tokenizer_before = ast.dump(tokenizer, include_attributes=False)

    class GenericOnly(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name in {"concrete", "concrete_file"}:
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in {"concrete", "concrete_file"}:
                node.func.id = "read_tokens"
            return node

    tree = GenericOnly().visit(tree)
    ast.fix_missing_locations(tree)
    tokenizer_after = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "tokenize")
    if ast.dump(tokenizer_after, include_attributes=False) != tokenizer_before:
        raise RuntimeError("Generic input transformation changed the tokenizer")
    if any(isinstance(node, ast.Name) and node.id in {"concrete", "concrete_file"} for node in ast.walk(tree)):
        raise RuntimeError("Generic input still references a concrete control")
    generic = "# Derived by tools/bench_stream_online.py: generic call plumbing only.\n" + ast.unparse(tree) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, source in (("generic", generic), ("concrete", original)):
        target = directory / f"stream_{name}.py"
        target.write_text(source)
        result[name] = {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        "text": source}
    return result


def summarize(samples):
    result = {}
    for name, records in samples.items():
        result[name] = {
            "wall_seconds": distribution([row["wall_seconds"] for row in records]),
            "inclusive_cpu_seconds": distribution([row["inclusive_cpu_seconds"] for row in records]),
            "phases": {},
        }
        for phase in ("cold", "warm", "shift", "recovery"):
            result[name]["phases"][phase] = {
                timer: distribution([row["phases"][phase][timer] for row in records])
                for timer in ("wall_seconds", "self_cpu_seconds")
            }
    return result


def paired_ratios(samples, baseline, selected):
    base = samples[baseline]
    target = samples[selected]
    result = {
        timer: distribution([left[timer] / right[timer] for left, right in zip(base, target)])
        for timer in ("wall_seconds", "inclusive_cpu_seconds")
    }
    result["phases"] = {
        phase: {
            timer: distribution([left["phases"][phase][timer] / right["phases"][phase][timer]
                                 for left, right in zip(base, target)])
            for timer in ("wall_seconds", "self_cpu_seconds")
        }
        for phase in ("cold", "warm", "shift", "recovery")
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, "-m", "pystachy"]))
    parser.add_argument("--online-compiler", type=Path, required=True,
                        help="native compiler executable invoked by each online host process")
    parser.add_argument("--cold", type=int, default=200)
    parser.add_argument("--warm", type=int, default=4000)
    parser.add_argument("--shift", type=int, default=40)
    parser.add_argument("--recovery", type=int, default=4000)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--jit-samples", type=int, default=3)
    parser.add_argument("--timing-cpu", type=int,
                        help="allowed CPU for timing; defaults to the first allowed CPU")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmarks/stream-online.json")
    args = parser.parse_args()
    if args.cold < 101 or min(args.warm, args.shift, args.recovery) < 1:
        parser.error("cold must exceed threshold 100; warm, shift and recovery must be positive")
    if args.samples < 3 or args.jit_samples < 1:
        parser.error("at least three AOT/online samples and one ordinary JIT sample are required")
    native_compiler = args.online_compiler.resolve()
    if not native_compiler.is_file() or not os.access(native_compiler, os.X_OK):
        parser.error("--online-compiler must be an executable native compiler")
    compiler = shlex.split(args.compiler)
    build = ROOT / "build/stream-online"
    build.mkdir(parents=True, exist_ok=True)
    inputs = write_inputs(build / "source")
    fixture = build / "input.txt"
    counts = {"cold": args.cold, "warm": args.warm, "shift": args.shift, "recovery": args.recovery}
    # The shift begins balanced, then runs files until one final memory call.
    half = args.shift // 2
    file_calls = 1 + half // 2 + args.shift - half - 1
    env = dict(os.environ, PYSTACHY_CLOSED_UNIONS="1", PYSTACHY_REFERENCE_UNIONS="1",
               PYSTACHY_FEEDBACK_FUNCTION="tokenize")
    for key in ("PYSTACHY_FEEDBACK_PROFILE", "PYSTACHY_FEEDBACK_RECORD", "PYSTACHY_FEEDBACK_COUNTERS",
                "PYSTACHY_FEEDBACK_OUT", "PYSTACHY_SKEW_PROFILE", "PYSTACHY_GC_STRESS",
                "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_IRFX", "PYSTACHY_SUMMARY_STATS",
                "PYSTACHY_ONLINE", "PYSTACHY_ONLINE_COMPILER", "PYSTACHY_ONLINE_STATS", "PYSTACHY_ONLINE_KEEP",
                "PYSTACHY_ONLINE_CHILD", "PYSTACHY_ONLINE_SITE", "PYSTACHY_ONLINE_MEMBER", "PYSTACHY_ONLINE_EXPECT"):
        env.pop(key, None)
    sources = [SOURCE, ROOT / "lib/shlex.py", ROOT / "lib/io.py", ROOT / "runtime.c",
               ROOT / "runtime.py", Path(__file__).resolve()]
    sources.extend(sorted((ROOT / "src/pystachy_compiler").glob("*.py")))
    sources.extend(Path(value["path"]) for value in inputs.values())

    def hashes():
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sources}

    source_hashes = hashes()
    native_hash = hashlib.sha256(native_compiler.read_bytes()).hexdigest()
    original_affinity = os.sched_getaffinity(0)
    cpu = min(original_affinity) if args.timing_cpu is None else args.timing_cpu
    if cpu not in original_affinity:
        parser.error(f"CPU {cpu} is not in the allowed affinity set")
    info = {
        "schema": "pystachy-stream-online-v1", "status": "incomplete",
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
        "compiler": compiler, "online_compiler": str(native_compiler),
        "online_compiler_sha256": native_hash,
        "git_head": execute(["git", "rev-parse", "HEAD"], env)["stdout"],
        "git_status": execute(["git", "status", "--short"], env)["stdout"],
        "counts": counts, "file_calls": file_calls, "samples": args.samples,
        "jit_samples": args.jit_samples, "timing_affinity_cpu": cpu,
        "allowed_affinity": sorted(original_affinity),
        "timers": {
            "wall_seconds": "external perf_counter includes process startup, all phases, and synchronous compilation/loading",
            "inclusive_cpu_seconds": "RUSAGE_CHILDREN delta for one waited process and its waited descendants",
            "phase_wall_seconds": "in-program perf_counter includes resets/reopens and synchronous online compilation/loading",
            "phase_self_cpu_seconds": "in-program process_time excludes spawned compiler CPU",
            "compile_cpu_s": "runtime wait4 child usage includes the compiler's waited descendants",
        },
        "workload": "Controlled stream mix; 9440 ASCII bytes and 544 tokens per parse. File phases include reopen I/O.",
        "online_policy": "threshold 100, minimum 90% share, one compilation attempt/site, fresh process per sample, no persistent cache",
        "inputs": inputs,
        "input_adaptation": "Generic and online hosts remove concrete wrapper definitions and replace their calls with the union wrapper. The tokenize AST is checked unchanged. Concrete control is a byte-exact copy of bench/stream_skew.py.",
        "builds": {}, "checks": {}, "samples_raw": {}, "summary": {},
    }
    llvm = env.get("PYSTACHY_LLVM", "")
    if llvm:
        info["llvm"] = execute([str(Path(llvm) / "clang"), "--version"], env)["stdout"].splitlines()[0]

    try:
        expected = execute([sys.executable, "-c", ORACLE, str(SOURCE), "check", "1", str(fixture)], env)["stdout"]
        info["checks"]["upstream_cpython"] = expected
        for name, input_name, options in (("generic", "generic", {}),
                                          ("online", "generic", {"PYSTACHY_ONLINE": "1",
                                                                  "PYSTACHY_ONLINE_COMPILER": str(native_compiler)}),
                                          ("concrete", "concrete", {})):
            target = build / name
            record = execute([*compiler, "build", inputs[input_name]["path"], "-o", str(target)], dict(env, **options))
            record.update({"executable_bytes": target.stat().st_size,
                           "executable_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                           "compile_options": options})
            info["builds"][name] = record
            actual = execute([str(target), "check", "1", str(fixture)], env)["stdout"]
            if actual != expected:
                raise RuntimeError(f"{name} differs from upstream CPython: {actual!r} != {expected!r}")
            info["checks"][name] = actual

        ir_path = build / "online.ll"
        execute([*compiler, "ir", inputs["generic"]["path"], "-o", str(ir_path)],
                dict(env, PYSTACHY_ONLINE="1", PYSTACHY_ONLINE_COMPILER=str(native_compiler)))
        host_ir = ir_path.read_text()
        tokenizer_definitions = re.findall(r"^define .*@f\.tokenize[^\n]*", host_ir, re.MULTILINE)
        wrapper = re.search(r"^define [^\n]*@f\.read_tokens\([^\n]*\n.*?^}",
                            host_ir, re.MULTILINE | re.DOTALL)
        if len(tokenizer_definitions) != 1 or re.search(r"^define .*@f\.concrete", host_ir, re.MULTILINE):
            raise RuntimeError("Online host contains a precompiled concrete tokenizer control")
        if wrapper is None or "@pys_online(" not in wrapper[0] or "call i64 %" not in wrapper[0]:
            raise RuntimeError("Online host does not dispatch through a runtime-installed entry")
        info["host_ir_check"] = {"path": str(ir_path),
                                 "sha256": hashlib.sha256(ir_path.read_bytes()).hexdigest(),
                                 "tokenizer_definitions": tokenizer_definitions,
                                 "read_tokens_ir": wrapper[0]}

        # The ordinary JIT driver's runtime object cache is shared by its run
        # processes. Prepare it explicitly so only the first measured generic
        # sample does not pay a one-time cache construction cost.
        preparation = execute([*compiler, "run", inputs["generic"]["path"],
                               "check", "1", str(fixture)], env)
        if preparation["stdout"] != expected:
            raise RuntimeError("Ordinary JIT cache preparation differs from upstream CPython")
        info["jit_cache_preparation"] = preparation

        def measure(name, command, mode, round_number, online=False):
            parameters = [mode, str(args.warm), str(fixture), str(args.cold), str(args.shift), str(args.recovery)]
            options = dict(env)
            stats = build / f"{name}-{round_number}.tsv"
            if online:
                stats.unlink(missing_ok=True)
                options.update(PYSTACHY_ONLINE_COMPILER=str(native_compiler), PYSTACHY_ONLINE_STATS=str(stats))
            record = execute([*command, *parameters], options)
            record["phases"] = parse_phases(record["stdout"], counts)
            if online:
                record["online_stats"] = parse_online_stats(stats, sum(counts.values()), file_calls)
                # The cold phase contains all compilation; expose its inclusive
                # CPU estimate without disguising the original self-only clock.
                cold_phase = record["phases"]["cold"]
                cold_phase["self_plus_compile_cpu_seconds"] = (
                    cold_phase["self_cpu_seconds"] + record["online_stats"]["site"]["compile_cpu_s"])
            info["samples_raw"].setdefault(name, []).append(record)

        os.sched_setaffinity(0, {cpu})
        try:
            variants = [("aot_generic", [str(build / "generic")], "phases", False),
                        ("online", [str(build / "online")], "phases", True),
                        ("aot_concrete", [str(build / "concrete")], "phases-static", False)]
            for round_number in range(args.samples):
                offset = round_number % len(variants)
                for name, command, mode, online in variants[offset:] + variants[:offset]:
                    measure(name, command, mode, round_number, online)
            # These ordinary JIT processes compile before program entry. Their
            # compilation is visible externally and excluded from phase clocks.
            jit = [("jit_generic", "generic", "phases"), ("jit_concrete", "concrete", "phases-static")]
            for round_number in range(args.jit_samples):
                offset = round_number % len(jit)
                for name, input_name, mode in jit[offset:] + jit[:offset]:
                    measure(name, [*compiler, "run", inputs[input_name]["path"]], mode, round_number)
        finally:
            os.sched_setaffinity(0, original_affinity)
        info["summary"] = summarize(info["samples_raw"])
        info["paired_ratios"] = {
            "aot_generic_over_online": paired_ratios(info["samples_raw"], "aot_generic", "online"),
            "aot_generic_over_concrete": paired_ratios(info["samples_raw"], "aot_generic", "aot_concrete"),
            "jit_generic_over_concrete": paired_ratios(info["samples_raw"], "jit_generic", "jit_concrete"),
        }
        if hashes() != source_hashes or hashlib.sha256(native_compiler.read_bytes()).hexdigest() != native_hash:
            raise RuntimeError("Compiler, runtime or workload changed during measurement; rerun")
        info["status"] = "complete"
    except Exception as error:
        info["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        info["source_sha256_before"] = source_hashes
        info["source_sha256_after"] = hashes()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "status": info["status"],
                      "paired_ratios": info["paired_ratios"]}, indent=2))


if __name__ == "__main__":
    main()
