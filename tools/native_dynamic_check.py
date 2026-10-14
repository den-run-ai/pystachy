"""Build and check a CPython-free scalar baseline with native specialization.

The orchestration/CPython oracle in this file is not part of the executor. Every
application subprocess uses the self-hosted compiler, a native Pystachy host and
a PATH containing only an explicit tool allowlist, with no Python executable.
Default: small correctness checks, no timing gates. --bench: repeated advisory
baseline/adaptive/static timings, separating cold compilation from warm kernels.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "examples/native_dynamic.py"
STATIC_SOURCE = ROOT / "examples/native_dynamic_workload.py"
LLVM_TOOLS = ("clang", "llvm-as", "llvm-link", "opt")
# The compiler's shell uses these; clang needs the system assembler/linker.
SHELL_TOOLS = ("sh", "sed", "mkdir", "rm", "mv", "ld", "as")


def checked_run(command, *, env, timeout=180):
    start = time.perf_counter()
    result = subprocess.run([str(part) for part in command], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    elapsed = time.perf_counter() - start
    if result.returncode:
        raise ValueError(f"command failed ({result.returncode}): {command!r}\n"
                         f"{result.stdout}{result.stderr}")
    return result, elapsed


def native_executable(path):
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"missing native executable: {path}")
    header = path.read_bytes()[:4]
    if header not in (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        raise ValueError(f"expected a self-hosted native executable, not a script: {path}")


def native_dependencies(compiler, build, env):
    if not sys.platform.startswith("linux"):
        return {}
    readelf = shutil.which("readelf")
    if not readelf:
        raise ValueError("readelf is required to check ELF dependencies on Linux")
    result = {}
    for path in (compiler, build / "host", build / "static", build / "libpsdyn.so"):
        inspection, _ = checked_run([readelf, "-d", path], env=env)
        needed = [line.split("[", 1)[1].split("]", 1)[0]
                  for line in inspection.stdout.splitlines() if "(NEEDED)" in line]
        if any("python" in name.lower() for name in needed):
            raise ValueError(f"Python shared library dependency found in {path}: {needed!r}")
        result[str(path)] = needed
    return result


def provenance(compiler, llvm, env):
    clang, _ = checked_run([llvm / "clang", "--version"], env=env)
    git = shutil.which("git")
    revision = "unknown"
    if git:
        result, _ = checked_run([git, "rev-parse", "HEAD"], env=env)
        revision = result.stdout.strip()
    cpu_model = platform.processor()
    try:
        cpu_model = next(line.split(":", 1)[1].strip()
                         for line in Path("/proc/cpuinfo").read_text().splitlines()
                         if line.startswith("model name"))
    except (OSError, StopIteration):
        pass
    sources = [SOURCE, STATIC_SOURCE, ROOT / "tools/native_dynamic.py",
               ROOT / "tools/native_dynamic_vm.py", ROOT / "tools/native_dynamic_types.py",
               ROOT / "tools/native_dynamic_loader.c", Path(__file__).resolve()]
    return {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_revision": revision, "platform": platform.platform(), "machine": platform.machine(),
            "cpu_model": cpu_model, "cpu_affinity": sorted(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity") else None,
            "orchestration_python": platform.python_version(), "clang": clang.stdout.splitlines()[0],
            "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
            "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sources}}


def llvm_directory(explicit):
    if explicit:
        directory = Path(explicit).resolve()
    elif os.environ.get("PYSTACHY_LLVM"):
        directory = Path(os.environ["PYSTACHY_LLVM"]).resolve()
    else:
        clang = shutil.which("clang-18") or shutil.which("clang")
        if not clang:
            raise ValueError("LLVM 18 tools not found; pass --llvm DIR or set PYSTACHY_LLVM")
        directory = Path(clang).resolve().parent
    for name in LLVM_TOOLS:
        if not (directory / name).is_file():
            raise ValueError(f"missing LLVM tool: {directory / name}")
    return directory


def isolated_environment(build, llvm):
    tools = build / "tool-bin"
    tools.mkdir(parents=True, exist_ok=True)
    allowed = {}
    for name in LLVM_TOOLS:
        allowed[name] = llvm / name
    for name in SHELL_TOOLS:
        path = shutil.which(name)
        if not path:
            raise ValueError(f"required shell/link tool not found: {name}")
        allowed[name] = Path(path)
    # Refuse stale additions: this directory is part of the no-Python assertion.
    for existing in tools.iterdir():
        if existing.name not in allowed:
            existing.unlink()
    for name, path in allowed.items():
        target = tools / name
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            raise ValueError(f"unexpected non-symlink in isolated tool directory: {target}")
        target.symlink_to(path)
    env = os.environ.copy()
    env.update({"PATH": str(tools), "PYSTACHY_LLVM": str(llvm),
                "PYSTACHY_HOME": str(ROOT), "PYSTACHY_PATH": str(ROOT),
                "PYSTACHY_CACHE": str(build / "compiler-cache")})
    old_library_path = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = str(build) + (":" + old_library_path if old_library_path else "")
    # These variables can inject Python-specific startup behavior into oracles,
    # but must not be necessary to the native executor.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    for name in ("python", "python3", "python3.13", "pypy", "pypy3"):
        if shutil.which(name, path=env["PATH"]):
            raise ValueError(f"Python executable found in isolated native PATH: {name}")
    return env


def prepare(compiler, llvm, build, env):
    clang = llvm / "clang"
    loader = ROOT / "tools/native_dynamic_loader.c"
    commands = [
        [compiler, "rt", ROOT / "runtime.py", "-o", build / "rt.ll"],
        [clang, "-O2", "-fexceptions", "-S", "-emit-llvm", ROOT / "runtime.c", "-o", build / "rtc.ll"],
        [llvm / "llvm-link", build / "rtc.ll", build / "rt.ll", "-o", build / "runtime.bc"],
        [clang, "-O2", "-fexceptions", "-DPYSTACHY_DYNAMIC_IMAGE", "-c", "-emit-llvm", loader,
         "-o", build / "image.bc"],
        [clang, "-O2", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror", loader,
         "-o", build / "libpsdyn.so", "-ldl"],
        [compiler, "build", ROOT / "tools/native_dynamic.py", "-o", build / "host"],
        [compiler, "build", STATIC_SOURCE, "-o", build / "static"],
    ]
    records = []
    for command in commands:
        result, elapsed = checked_run(command, env=env)
        records.append({"command": [str(part) for part in command], "wall_s": elapsed})
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    native_executable(build / "host")
    native_executable(build / "static")
    return records


def parse_output(text):
    results = []
    errors = []
    stats = None
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 5 and parts[0] == "RESULT":
            seconds = float(parts[4])
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError(f"invalid kernel time: {parts[4]!r}")
            results.append({"function": parts[1], "tag": parts[2], "value": parts[3],
                            "kernel_s": seconds})
        elif len(parts) == 3 and parts[0] == "ERROR":
            errors.append({"function": parts[1], "message": parts[2]})
        elif parts[0] == "STATS" and stats is None:
            stats = {}
            for part in parts[1:]:
                key, value = part.split("=", 1)
                stats[key] = float(value) if key == "compile_seconds" else int(value)
        else:
            raise ValueError(f"unexpected native output: {line!r}")
    return {"results": results, "errors": errors, "stats": stats}


def run_plan(build, source, name, lines, mode, compiler, llvm, env, *, warmup=3,
             maxvariants=2, attempts=4):
    plan = build / (name + ".plan")
    plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = [build / "host", source, plan, mode, compiler, llvm, build,
               str(warmup), str(maxvariants), str(attempts)]
    result, elapsed = checked_run(command, env=env)
    if result.stderr:
        raise ValueError(f"unexpected native diagnostics: {result.stderr!r}")
    report = parse_output(result.stdout)
    if report["stats"] is None:
        raise ValueError("missing native dispatcher counters")
    report.update({"command": [str(part) for part in command], "wall_s": elapsed})
    return report


def result_values(report):
    return [(row["function"], row["tag"], row["value"]) for row in report["results"]]


def capped_profiles(build, compiler, llvm, env):
    report = run_plan(build, SOURCE, "rare-first-capped", ["echo 6 str:rare", "echo 6 bool:true",
                      "echo 6 None:", "add 6 int:2 int:3", "add 6 float:2.0 float:3.0",
                      "add 6 int:2 float:3.0"], "adaptive", compiler, llvm, env)
    expected = [("echo", "str", "'rare'"), ("echo", "bool", "True"),
                ("echo", "None", "None"), ("add", "int", "5"),
                ("add", "float", "5.0"), ("add", "float", "5.0")]
    if result_values(report) != expected or report["errors"]:
        raise ValueError("rare-first or capped specialization changed baseline results")
    stats = report["stats"]
    if stats["variants"] != 2 or stats["attempts"] != 2 or stats["profiles"] != 3 or stats["native"] < 1:
        raise ValueError(f"rare signatures consumed hot numeric slots, or cap was exceeded: {stats!r}")
    return report


def conservative_rejections(build, compiler, llvm, env):
    report = run_plan(build, SOURCE, "conservative-regions", ["float_floor 6 float:3.0",
                      "float_floor 2 float:-3.0", "float_remainder 6 float:3.0",
                      "float_remainder 2 float:-3.0", "annotated 6 float:2.5"],
                      "adaptive", compiler, llvm, env)
    expected = [("float_floor", "float", "1.0"), ("float_remainder", "float", "1.0"),
                ("annotated", "float", "2.5")]
    # This baseline intentionally supports // and % for integers only. A native
    # region must not quietly start accepting an unsupported branch after warmup.
    if result_values(report) != expected or len(report["errors"]) != 2:
        raise ValueError("unvisited branch or mismatched annotation changed baseline semantics")
    if any("requires integer operands" not in row["message"] for row in report["errors"]):
        raise ValueError("unsupported float floor/remainder changed their baseline errors")
    if report["stats"]["variants"] != 0 or report["stats"]["rejections"] != 3:
        raise ValueError("float-floor region or mismatched annotation was unsafely specialized")
    return report


def implicit_none_replay(build, compiler, llvm, env):
    report = run_plan(build, SOURCE, "implicit-none", ["optional 6 int:1", "optional 1 int:-1"],
                      "adaptive", compiler, llvm, env)
    if result_values(report) != [("optional", "int", "1"), ("optional", "None", "None")] or report["errors"]:
        raise ValueError("native fallthrough did not replay the pure baseline to return None")
    if report["stats"]["native"] < 1 or report["stats"]["baseline"] != 4:
        raise ValueError("native fallthrough replay path was not exercised")
    return report


def baseline_edges(build, compiler, llvm, env):
    source = build / "baseline-edges.py"
    source.write_text("""def minimum():
    return -9223372036854775808

def multiply(x, y):
    return x * y

def compare_large(x, y):
    return x == y

def short_circuit(x):
    return x or (1 // 0)

def range_edge():
    total = 0
    for value in range(9223372036854775806, 9223372036854775807, 2):
        total = total + 1
    return total

def loop_control(n):
    total = 0
    for i in range(n):
        if i == 1:
            continue
        if i == 4:
            break
        total = total + i
    else:
        total = total + 100
    return total
""", encoding="utf-8")
    report = run_plan(build, source, "baseline-edges", ["minimum 1", "compare_large 1 int:9223372036854775807 float:9223372036854775807",
                      "short_circuit 1 int:3", "range_edge 1", "loop_control 1 int:3",
                      "loop_control 1 int:8", "multiply 1 int:-4611686018427387904 int:-2"],
                      "baseline", compiler, llvm, env)
    expected = [("minimum", "int", "-9223372036854775808"), ("compare_large", "bool", "False"),
                ("short_circuit", "int", "3"), ("range_edge", "int", "1"),
                ("loop_control", "int", "102"), ("loop_control", "int", "5")]
    if result_values(report) != expected or len(report["errors"]) != 1:
        raise ValueError(f"tagged baseline edge-case semantics changed: {report!r}")
    if "overflow" not in report["errors"][0]["message"].lower():
        raise ValueError("signed i64 multiplication overflow was not checked")
    return report


def rejected_sources(build, compiler, llvm, env):
    fixtures = {
        "imports": "import os\n\ndef f(x):\n    return x\n",
        "side_effect": "def f(x):\n    return print(x)\n",
        "default_parameter": "def f(x=1):\n    return x\n",
        "runtime_symbol": "def pys_floordiv(x: int, y: int) -> int:\n    return 123\n",
        "generated_symbol": "def _psdyn_result(x):\n    return x\n",
        "loader_symbol": "def psdyn_image_call(x):\n    return x\n",
    }
    plan = build / "rejected.plan"
    plan.write_text("f 1 int:1\n", encoding="utf-8")
    records = {}
    for name, text in fixtures.items():
        source = build / ("rejected-" + name + ".py")
        source.write_text(text, encoding="utf-8")
        result = subprocess.run([str(part) for part in [build / "host", source, plan, "adaptive",
                               compiler, llvm, build]], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0 or "native dynamic subset" not in result.stderr:
            raise ValueError(f"unsupported/impure source was not rejected before execution: {name}: "
                             f"{result.stdout}{result.stderr}")
        records[name] = {"returncode": result.returncode, "diagnostic": result.stderr.strip()}
    return records


def oracle():
    # A reference oracle only. Native runs neither load nor import this module.
    spec = importlib.util.spec_from_file_location("native_dynamic_oracle", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke(build, compiler, llvm, env):
    reference = oracle()
    calls = [
        ("sumsq", 6, [25]),
        ("weighted_sum", 6, [3, 25]),
        ("weighted_sum", 6, [1.5, 25]),
        ("add", 6, [7, 9]),
        ("add", 6, [1.5, 2.5]),
        ("add", 2, [10, 20]),
        ("add", 2, [True, False]),
        ("add", 2, ["hello", "world"]),
        ("echo", 2, [None]),
        ("mixed_local", 6, [4]),
        ("mixed_local", 2, [-4]),
    ]
    lines = []
    expected = []
    for name, repeats, arguments in calls:
        encoded = []
        for argument in arguments:
            if argument is None:
                encoded.append("None:")
            elif isinstance(argument, bool):
                encoded.append("bool:" + str(argument).lower())
            else:
                encoded.append(type(argument).__name__ + ":" + str(argument))
        lines.append(" ".join([name, str(repeats), *encoded]))
        value = getattr(reference, name)(*arguments)
        expected.append((name, "None" if value is None else type(value).__name__, repr(value)))
    baseline = run_plan(build, SOURCE, "smoke-baseline", lines, "baseline", compiler, llvm, env)
    adaptive = run_plan(build, SOURCE, "smoke-adaptive", lines, "adaptive", compiler, llvm, env,
                        maxvariants=8, attempts=10)
    if result_values(baseline) != expected or result_values(adaptive) != expected:
        raise ValueError(f"baseline/adaptive differs from CPython oracle: expected={expected!r}, "
                         f"baseline={result_values(baseline)!r}, adaptive={result_values(adaptive)!r}")
    if baseline["errors"] or adaptive["errors"]:
        raise ValueError("unexpected native execution errors")
    if baseline["stats"]["native"] != 0 or baseline["stats"]["attempts"] != 0:
        raise ValueError("baseline mode attempted or entered specialization")
    if adaptive["stats"]["native"] < 1 or adaptive["stats"]["attempts"] < 2:
        raise ValueError("adaptive mode never entered native code for observed scalar types")
    if adaptive["stats"]["rejections"] < 1 or adaptive["stats"]["misses"] < 1:
        raise ValueError("dynamic locals/tag guard fallback was not exercised")

    # The host itself is already native. Force runtime specialization compilation
    # to fail to verify that successful application execution still has a baseline.
    failing_compiler = Path(shutil.which("false") or "/bin/false")
    failed = run_plan(build, SOURCE, "compile-failure", ["sumsq 6 int:25"], "adaptive",
                      failing_compiler, llvm, env)
    if result_values(failed) != expected[:1] or failed["errors"]:
        raise ValueError("failed specialization did not preserve baseline execution")
    if failed["stats"]["failures"] < 1 or failed["stats"]["native"] != 0:
        raise ValueError("runtime compiler failure fallback was not exercised")

    errors = run_plan(build, SOURCE, "checked-errors", ["divide 6 int:12 int:3",
                      "divide 1 int:12 int:0", "add 6 int:4 int:5",
                      "add 1 int:9223372036854775807 int:1"], "adaptive", compiler, llvm, env)
    if result_values(errors) != [("divide", "int", "4"), ("add", "int", "9")]:
        raise ValueError("exception replay changed the successful results")
    if len(errors["errors"]) != 2 or errors["stats"]["native"] < 1:
        raise ValueError("native error replay was not exercised")
    messages = " ".join(row["message"] for row in errors["errors"])
    if "zero" not in messages.lower() or "overflow" not in messages.lower():
        raise ValueError(f"unexpected checked scalar errors: {messages}")
    return {"baseline": baseline, "adaptive": adaptive, "compiler_failure": failed,
            "checked_errors": errors, "rare_first_capped": capped_profiles(build, compiler, llvm, env),
            "conservative_rejections": conservative_rejections(build, compiler, llvm, env),
            "implicit_none_replay": implicit_none_replay(build, compiler, llvm, env),
            "baseline_edges": baseline_edges(build, compiler, llvm, env),
            "rejected_sources": rejected_sources(build, compiler, llvm, env)}


def benchmark(build, compiler, llvm, env, runs, n, repeats):
    records = {"baseline": [], "adaptive": [], "static": []}
    expected = sum((n + i % 7 - 1) * (n + i % 7) * (2 * (n + i % 7) - 1) // 6
                   for i in range(repeats))
    for round_index in range(runs):
        order = list(records) if round_index % 2 == 0 else list(reversed(records))
        for mode in order:
            if mode == "static":
                result, wall_s = checked_run([build / "static", str(n), str(repeats), "4"], env=env)
                report = parse_output(result.stdout)
                report["wall_s"] = wall_s
            else:
                report = run_plan(build, SOURCE, f"bench-{round_index}-{mode}",
                                  [f"batch 4 int:{n} int:{repeats}", f"batch 1 int:{n} int:{repeats}"],
                                  mode, compiler, llvm, env)
            row = report["results"][-1]
            if (row["function"], row["tag"], row["value"]) != ("batch", "int", str(expected)):
                raise ValueError(f"benchmark output differs in {mode}: {row!r}")
            if report["errors"]:
                raise ValueError(f"benchmark execution failed in {mode}")
            if mode == "adaptive":
                if report["stats"]["native"] < 1 or report["stats"]["variants"] != 1 or report["stats"]["attempts"] != 1:
                    raise ValueError("adaptive benchmark did not actually execute its native specialization")
            elif mode == "baseline":
                if report["stats"]["native"] != 0 or report["stats"]["attempts"] != 0:
                    raise ValueError("baseline benchmark unexpectedly specialized")
            records[mode].append(report)
    medians = {mode: statistics.median(record["results"][-1]["kernel_s"] for record in samples)
               for mode, samples in records.items()}
    return {"runs": runs, "input_n": n, "calls": repeats, "records": records,
            "warm_kernel_median_s": medians,
            "adaptive_cold_compile_median_s": statistics.median(
                record["stats"]["compile_seconds"] for record in records["adaptive"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy",
                        help="self-hosted native Pystachy compiler")
    parser.add_argument("--llvm", help="LLVM 18 executable directory")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/native-dynamic")
    parser.add_argument("--skip-build", action="store_true", help="reuse prepared native artifacts")
    parser.add_argument("--bench", action="store_true", help="run advisory warm kernel measurements")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--calls", type=int, default=20)
    parser.add_argument("--json", type=Path, help="save successful check/benchmark report")
    args = parser.parse_args()
    if args.runs < 1 or args.n < 1 or args.calls < 1:
        parser.error("--runs, --n and --calls must be positive")
    compiler = args.compiler.resolve()
    native_executable(compiler)
    llvm = llvm_directory(args.llvm)
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    env = isolated_environment(build, llvm)
    setup = [] if args.skip_build else prepare(compiler, llvm, build, env)
    dependencies = native_dependencies(compiler, build, env)
    checks = smoke(build, compiler, llvm, env)
    report = {"result": "pass", "executor": "native Pystachy; no Python executable on runtime PATH",
              "compiler": str(compiler), "llvm": str(llvm), "runtime_path": env["PATH"],
              "setup": setup, "native_dependencies": dependencies, "checks": checks,
              "provenance": provenance(compiler, llvm, env)}
    print("native-dynamic: baseline, specialization, phase changes, guards, compile failure and checked errors pass")
    if args.bench:
        report["benchmark"] = benchmark(build, compiler, llvm, env, args.runs, args.n, args.calls)
        timings = report["benchmark"]["warm_kernel_median_s"]
        print(f"warm kernel ({args.calls} calls, n={args.n}): "
              + ", ".join(f"{mode}={seconds:.6f}s" for mode, seconds in timings.items()))
        print(f"adaptive cold compilation: {report['benchmark']['adaptive_cold_compile_median_s']:.6f}s")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        sys.exit(f"native-dynamic-check: {error}")
