"""Correctness-gated JSON parsing/processing benchmark; see docs/json-benchmark.md.

No downloads or performance thresholds. The source-written guarded mode is a
control, not a claim of automatic profile-guided or online specialization.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import statistics
import sys
import tempfile
import time

from bench_extended import digest, execute, positive, summary

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/json_records.py"
PROFILES = ("skewed", "mixed", "changing")
TEXTS = ("utf8", "ascii", "escaped")
# cpython and pypy decode with their own stdlib json. The -lib modes run Pystachy's
# json.py source on that interpreter instead: one parser, three ways to execute it.
MODES = ("cpython", "pypy", "jit", "aot", "cpython-lib", "pypy-lib")
PHASES = ("all", "predecoded")


def fixture(records, profile, text="utf8"):
    """Deterministic input with skew, broad alternatives and a late phase shift.

    text is utf8 (raw non-ASCII), escaped (the same values as \\u escapes) or
    ascii (one ASCII character for each non-ASCII one, so the values keep their
    lengths in characters and the processing checksum of utf8).
    """
    accent, region = ("eXR", "dy") if text == "ascii" else ("é雪🚀", "地域")
    result = []
    for index in range(records):
        slot = index % 100
        if profile == "mixed" or profile == "changing" and index >= records // 2:
            slot = (index % 8) + 92
        record = {"id": index, "details": {
            "name": "event-" + str(index) + "-" + accent,
            "tags": ["api", "paid" if index % 2 else "pending", region],
        }}
        amount = index % 1000
        if slot < 92:
            record["amount"] = amount
        elif slot < 94:
            record["amount"] = amount + 0.25
        elif slot == 94:
            record["amount"] = None
        elif slot == 95:
            pass  # Missing field: .get() must preserve the null fallback.
        elif slot == 96:
            record["amount"] = "pending"
        elif slot == 97:
            record["amount"] = True
        elif slot == 98:
            record["amount"] = [amount, None]
        else:
            record["amount"] = {"units": amount}
        result.append(record)
    return json.dumps(result, ensure_ascii=text != "utf8", separators=(",", ":"))


def parse_output(output, samples, expected=None, phase="all", encoded=None):
    """Warmup and sample rows of one run, every checksum compared with CPython's.

    expected is the reference [documents, processed, parsed and processed]; a
    predecoded run reports only its processed sum and the length and digest of its
    dumps() text, so it needs the reference and those of CPython's text (encoded).
    """
    lines = [line.split() for line in output.splitlines()]
    if not lines or len(lines[0]) != 3 or lines[0][0] != "JSON_WARMUP":
        raise ValueError("missing JSON warmup row")
    warmup = {"rounds": int(lines[0][1]), "seconds": int(lines[0][2]) / 1e9}
    if warmup["rounds"] < 1 or warmup["seconds"] < 0:
        raise ValueError(f"invalid JSON warmup: {lines[0]}")
    if len(lines) != samples + 1:
        raise ValueError("missing or extra JSON sample rows")
    if phase == "all":
        tag, width, names = "JSON_SAMPLE", 8, ("parse", "process", "end_to_end")
    elif expected is None or encoded is None:
        raise ValueError("a predecoded run needs the reference checksum and encoded length")
    else:
        tag, width, names = "JSON_PREDECODED", 8, ("process", "rebuild", "encode")
    timings = {name: [] for name in names}
    for index, row in enumerate(lines[1:]):
        if len(row) != width or row[0] != tag or int(row[1]) != index:
            raise ValueError(f"invalid JSON sample: {row}")
        if phase == "all":
            checksum = [int(value) for value in row[2:5]]
            if expected is None:
                expected = checksum
            if checksum != expected:
                raise ValueError(f"checksum {checksum} != reference {expected}")
        elif int(row[2]) != expected[1]:
            raise ValueError(f"checksum {row[2]} != reference {expected[1]}")
        elif [int(value) for value in row[3:5]] != encoded:
            raise ValueError(f"encoded length and digest {row[3:5]} != reference {encoded}")
        elapsed = [int(value) for value in row[width - len(names):]]
        if any(value < 0 for value in elapsed):
            raise ValueError("negative timing")
        for name, ns in zip(timings, elapsed):
            timings[name].append(ns / 1e9)
    return {"checksum": expected, "warmup": warmup, "timings_s": timings}


def measured(command, env, timeout, directory):
    # GNU time is optional; do not confuse cumulative RUSAGE_CHILDREN with a
    # particular process's peak. RSS includes LLVM children for JIT/build runs.
    timer = Path("/usr/bin/time")
    rss = directory / "peak-rss.txt"
    wrapped = [str(timer), "-f", "%M", "-o", str(rss), *command] if timer.exists() and sys.platform == "linux" else command
    result = execute(wrapped, env, timeout)
    result["peak_rss_kib"] = int(rss.read_text().strip()) if wrapped is not command else None
    result["command"] = command
    return result


def tool_version(tool, env, timeout):
    directory = Path(env.get("PYSTACHY_LLVM", ""))
    command = str(directory / tool) if str(directory) != "." else tool
    try:
        return execute([command, "--version"], env, timeout)["stdout"]
    except (OSError, RuntimeError) as exc:
        return "unavailable: " + str(exc)


def interpreter(path, implementation, env, timeout):
    """Version and identity of an interpreter, refusing one of another implementation."""
    code = "import platform, sys; print(platform.python_implementation()); print(' '.join(sys.version.split()))"
    lines = execute([path, "-c", code], env, timeout)["stdout"].splitlines()
    if not lines or lines[0] != implementation:
        raise ValueError(f"{path} is not {implementation}: {lines[:1]}")
    resolved = Path(shutil.which(path) or path)
    return {"path": str(path), "implementation": lines[0], "version": lines[1],
            "sha256": digest(resolved) if resolved.is_file() else None}


def encoding(text):
    """The length and bench/json_records.py's digest of CPython's dumps() text of a document."""
    spec = importlib.util.spec_from_file_location("json_records", SOURCE)
    records = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(records)
    encoded = json.dumps(json.loads(text))
    return [len(encoded), records.digest(encoded)]


def compiler_home(compiler, env):
    """The resource directory the compiler reads lib/ from, as driver.compiler_home() finds it.

    The compiler runs with ROOT as its working directory: a relative PYSTACHY_HOME, a hosted
    compiler (python -m pystachy) and a compiler found on PATH all resolve from there.
    """
    if env.get("PYSTACHY_HOME"):
        return (ROOT / env["PYSTACHY_HOME"]).resolve()
    if "-m" in compiler or "/" not in compiler[0]:
        home = ROOT
    else:
        home = (ROOT / compiler[0]).resolve().parent
    return home if (home / "runtime.c").exists() else home.parent


def compiled_json_module(env, compiler):
    """The json.py that the compiler compiles for bench/json_records.py.

    It searches the program's directory, PYSTACHY_PATH (relative entries from its working
    directory, ROOT), then lib/ of its home, as before/after runs rely on.
    """
    dirs = [SOURCE.parent] + [ROOT / d for d in env.get("PYSTACHY_PATH", "").split(":") if d]
    for directory in dirs + [compiler_home(compiler, env) / "lib"]:
        if (directory / "json.py").is_file():
            return (directory / "json.py").resolve()
    raise ValueError("no json.py on Pystachy's module path")


def imported_json(python, env, timeout):
    """The json module that python imports for bench/json_records.py: its directory comes
    first on the module path, as it does for the measured runs."""
    code = "import sys; sys.path[0] = sys.argv[1]; import json; print(json.__file__)"
    found = execute([python, "-c", code, str(SOURCE.parent)], env, timeout)["stdout"].strip()
    return Path(found).resolve()


def library_module(directory, module, pypy):
    """A directory whose json.py is Pystachy's parser source, for the -lib modes."""
    text = module.read_text(encoding="utf-8")
    if pypy:
        # PyPy 3.11 lacks the PEP 695 alias statement; annotations need only a name.
        text, count = re.subn(r"^type JSONValue = .*$", "JSONValue = object  # PyPy 3.11", text, flags=re.M)
        if count != 1:
            raise ValueError("JSONValue alias not found in " + str(module))
    target = directory / ("pypy-lib" if pypy else "cpython-lib")
    target.mkdir()
    (target / "json.py").write_text(text, encoding="utf-8")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command; no shell evaluation")
    parser.add_argument("--pypy", default=shutil.which("pypy3"), help="PyPy 3 executable for the pypy modes")
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--texts", nargs="+", choices=TEXTS, default=["utf8"])
    parser.add_argument("--modes", nargs="+", choices=MODES, default=["cpython", "jit", "aot"])
    parser.add_argument("--phases", nargs="+", choices=PHASES, default=list(PHASES))
    parser.add_argument("--records", type=positive, default=2000)
    parser.add_argument("--iterations", type=positive, default=5)
    parser.add_argument("--samples", type=positive, default=3)
    parser.add_argument("--processes", type=positive, default=3)
    parser.add_argument("--warmup-ms", type=int, default=2000,
                        help="run the measured operations this long before sampling (at least once)")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--smoke", action="store_true",
                        help="100 records, one iteration/sample/process, no warmup; correctness only")
    parser.add_argument("--json", type=Path, default=ROOT / "build/json-benchmark.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive and finite")
    if args.warmup_ms < 0:
        parser.error("warmup must be nonnegative")
    pinned = (ROOT / ".python-version").read_text().strip()
    if ".".join(str(part) for part in sys.version_info[:3]) != pinned:
        parser.error(f"run the controller with pinned CPython {pinned}: it is the checksum reference")
    if any(mode.startswith("pypy") for mode in args.modes) and not args.pypy:
        parser.error("the pypy modes need --pypy (no pypy3 on PATH)")
    if args.smoke:
        args.records, args.iterations, args.samples, args.processes, args.warmup_ms = 100, 1, 1, 1, 0
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    if "/" in compiler[0]:
        compiler[0] = str((ROOT / compiler[0]).resolve())
    env = dict(os.environ, PYTHONHASHSEED="0")
    plain = {key: value for key, value in env.items() if key != "PYTHONPATH"}
    native = "jit" in args.modes or "aot" in args.modes
    module = compiled_json_module(env, compiler)
    report = {
        "schema_version": 3, "status": "running", "cases": [],
        "scope": "native JSON baseline and source-written guarded control; no compiler specialization",
        "settings": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "metadata": {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "platform": platform.platform(), "python": sys.version,
                     "cpu_count": os.cpu_count(),
                     "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                     "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
                     "cpython": interpreter(sys.executable, "CPython", plain, args.timeout),
                     "pypy": interpreter(args.pypy, "PyPy", plain, args.timeout)
                     if any(mode.startswith("pypy") for mode in args.modes) else None,
                     "compiler_command": compiler,
                     "compiler_binary_sha256": digest(Path(compiler[0])) if Path(compiler[0]).is_file() else None,
                     "json_module": {"path": str(module), "sha256": digest(module)},
                     "git_revision": execute(["git", "rev-parse", "HEAD"], env, args.timeout)["stdout"].strip(),
                     "git_status": execute(["git", "status", "--porcelain"], env, args.timeout)["stdout"],
                     "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                                       [SOURCE, ROOT / "tools/bench_json.py", ROOT / "runtime.c", ROOT / "runtime.py"] +
                                       sorted((ROOT / "src").rglob("*.py")) + list((ROOT / "lib").glob("json.py"))},
                     "environment": {key: value for key, value in env.items() if key.startswith("PYSTACHY_")}},
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-json-bench-") as tmp:
            directory = Path(tmp)
            executable = directory / "json_records"
            prefixes = {"cpython": ([sys.executable, str(SOURCE)], plain), "jit": (compiler + ["run", str(SOURCE)], env),
                        "aot": ([str(executable)], env), "pypy": ([str(args.pypy), str(SOURCE)], plain)}
            imports = {}
            for mode in ("cpython", "pypy", "cpython-lib", "pypy-lib"):
                if mode not in args.modes:
                    continue
                python = sys.executable if mode.startswith("cpython") else str(args.pypy)
                target = library_module(directory, module, mode == "pypy-lib") if mode.endswith("-lib") else None
                run_env = dict(plain, PYTHONPATH=str(target)) if target else plain
                found = imported_json(python, run_env, args.timeout)
                if target and found != (target / "json.py").resolve():
                    raise ValueError(f"{mode} imports {found}, not Pystachy's json.py")
                if not target and (ROOT in found.parents or found.parent.name != "json"):
                    raise ValueError(f"{mode} imports {found}, not its standard library's json")
                imports[mode] = str(found)
                prefixes[mode] = ([python, str(SOURCE)], run_env)
            report["metadata"]["json_imports"] = imports
            if native:
                report["metadata"]["llvm"] = {
                    tool: tool_version(tool, env, args.timeout)
                    for tool in ("clang", "opt", "lli", "llvm-link")
                }
                warm = directory / "startup.py"
                warm.write_text("pass\n")
                report["runtime_cache_prime"] = execute(compiler + ["run", str(warm)], env, args.timeout)
            if "aot" in args.modes:
                report["aot_build"] = measured(compiler + ["build", str(SOURCE), "-o", str(executable)], env, args.timeout, directory)
                report["aot_bytes"] = executable.stat().st_size
            for profile in args.profiles:
                for text in args.texts:
                    path = directory / f"{profile}-{text}.json"
                    path.write_text(fixture(args.records, profile, text), encoding="utf-8")
                    common = [str(args.iterations), str(args.samples), str(args.warmup_ms)]
                    oracle = execute([sys.executable, str(SOURCE), str(path), "generic", *common[:2], "0", "all"],
                                     plain, args.timeout)
                    expected = parse_output(oracle["stdout"], args.samples)["checksum"]
                    encoded = encoding(path.read_text(encoding="utf-8"))
                    case = {"profile": profile, "text": text, "input_sha256": digest(path),
                            "input_bytes": path.stat().st_size, "oracle": oracle, "checksum": expected,
                            "encoded_chars": encoded[0], "encoded_digest": encoded[1], "runs": [], "summary": {}}
                    report["cases"].append(case)
                    order = [(mode, algorithm, phase) for mode in args.modes
                             for algorithm in ("generic", "handguarded") for phase in args.phases]
                    for repeat in range(args.processes):
                        rotated = order[repeat % len(order):] + order[:repeat % len(order)]
                        for mode, algorithm, phase in rotated:
                            prefix, run_env = prefixes[mode]
                            result = measured(prefix + [str(path), algorithm, *common, phase], run_env, args.timeout, directory)
                            result.update(parse_output(result["stdout"], args.samples, expected, phase, encoded))
                            result.update(mode=mode, algorithm=algorithm, phase=phase, repeat=repeat)
                            case["runs"].append(result)
                    for mode, algorithm, phase in order:
                        runs = [run for run in case["runs"] if (run["mode"], run["algorithm"], run["phase"]) == (mode, algorithm, phase)]
                        values = {"wall": summary([run["wall_s"] for run in runs]),
                                  "warmup_rounds": summary([run["warmup"]["rounds"] for run in runs])}
                        for name in runs[0]["timings_s"]:
                            values[name] = summary([statistics.median(run["timings_s"][name]) / args.iterations for run in runs])
                        case["summary"]["/".join((mode, algorithm, phase))] = values
                        print(profile, text, mode, algorithm, phase, "ms/document",
                              {name: round(values[name]["median_s"] * 1e3, 3) for name in runs[0]["timings_s"]})
                    if "aot" in args.modes:
                        probe_env = dict(env, PYSTACHY_GC="stats")
                        probe = execute([str(executable), str(path), "generic", *common[:2], "0", "all"], probe_env, args.timeout)
                        parse_output(probe["stdout"], args.samples, expected)
                        case["aot_gc_probe"] = probe
                        case["aot_gc_probe"]["environment_overrides"] = {"PYSTACHY_GC": "stats"}
            report["status"] = "passed"
    except (OSError, RuntimeError, ValueError) as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
