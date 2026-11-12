"""Check and measure typed match dispatch against equivalent handwritten branches."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from bench_extended import execute  # noqa: E402

VARIANTS = ("match", "if")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def positive(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def checked(command, env, timeout, count, expected=None):
    record = execute(command, env, timeout)
    rows = record["stdout"].splitlines()
    if len(rows) != 2 or int(rows[1]) != count:
        raise ValueError(f"invalid checksum/count output: {record['stdout']!r}")
    checksum = int(rows[0])
    if expected is not None and checksum != expected:
        raise ValueError(f"checksum {checksum} != CPython/reference {expected}")
    timing = [line.split() for line in record["stderr"].splitlines()]
    if (len(timing) != 1 or len(timing[0]) != 2 or timing[0][0] != "kernel_wall_ns"
            or int(timing[0][1]) <= 0):
        raise ValueError(f"missing/invalid kernel timing: {record['stderr']!r}")
    record.update(checksum=checksum, count=count, kernel_wall_ns=int(timing[0][1]))
    return record


def summaries(pairs):
    result = {}
    for metric in ("kernel_wall_ns", "wall_s"):
        ratios = [pair["if"][metric] / pair["match"][metric] for pair in pairs]
        result[metric] = {
            "median_if_over_match": statistics.median(ratios),
            "min_if_over_match": min(ratios),
            "max_if_over_match": max(ratios),
            "samples": len(ratios),
        }
    return result


def metadata(compiler, env, timeout):
    def info(command):
        return execute(command, env, timeout)["stdout"].strip()
    sources = [ROOT / name for name in ("pystachy.py", "runtime.py", "runtime.c", "VERSION",
                                       "tools/bench_extended.py")]
    for directory in ("src", "lib", "mpz", "ryu", "bench/match_dispatch"):
        sources.extend(path for path in (ROOT / directory).rglob("*")
                       if path.suffix in (".py", ".c", ".h"))
    llvm = info([sys.executable, "-c", "from pystachy import llvm_dir; print(llvm_dir())"])
    llvm_tools = {}
    if llvm:
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as"):
            path = (ROOT / llvm / name).resolve()
            llvm_tools[name] = {"version": info([str(path), "--version"]), "sha256": digest(path)}
    cpuinfo = Path("/proc/cpuinfo")
    cpu_model = platform.processor()
    if cpuinfo.is_file():
        cpu_model = next((line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                          if line.startswith("model name")), cpu_model)
    return {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision": info(["git", "rev-parse", "HEAD"]),
        "git_status": info(["git", "status", "--porcelain=v1", "--untracked-files=all"]),
        "platform": platform.platform(), "cpu_count": os.cpu_count(), "cpu_model": cpu_model,
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "load_average_start": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "python": sys.version, "python_executable": sys.executable,
        "repository_python_version": (ROOT / ".python-version").read_text().strip(),
        "compiler_command": compiler, "llvm": llvm_tools,
        "environment": {key: value for key, value in env.items() if key.startswith("PYSTACHY_")
                        or key in ("PYTHONHASHSEED", "LANG", "LC_ALL")},
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in sorted(set(sources))},
        "compiler_executable_sha256": digest(Path(compiler[0])) if Path(compiler[0]).is_file() else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command, no shell evaluation")
    parser.add_argument("--modes", nargs="+", choices=("cpython", "jit", "aot"), default=["cpython", "jit", "aot"])
    parser.add_argument("--kinds", nargs="+", choices=("literal", "tuple", "dataclass"), default=["literal", "tuple", "dataclass"])
    parser.add_argument("--shapes", nargs="+", choices=("mixed", "skewed"), default=["mixed", "skewed"])
    parser.add_argument("--samples", type=positive, default=5)
    parser.add_argument("--loops", type=positive, default=1000)
    parser.add_argument("--size", type=positive, default=4096)
    parser.add_argument("--cpu", type=int, help="pin to this allowed CPU; default: lowest allowed CPU")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--keep", type=Path, help="new directory retaining the executable and private runtime cache")
    parser.add_argument("--json", type=Path, default=ROOT / "build/match-dispatch.json")
    parser.add_argument("--smoke", action="store_true", help="one pair, 3 loops, 257 items; correctness only")
    args = parser.parse_args(argv)
    for name in ("modes", "kinds", "shapes"):
        values = getattr(args, name)
        if len(values) != len(set(values)):
            parser.error(f"{name} must not contain duplicates")
    if args.size > 1000000 or args.loops > 1000000 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("size/loops must not exceed 1000000; timeout must be positive and finite")
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("compiler command cannot be empty")
    if "/" in compiler[0]:
        compiler[0] = str((ROOT / compiler[0]).resolve())
    affinity = os.sched_getaffinity(0) if hasattr(os, "sched_getaffinity") else None
    if args.cpu is not None and (affinity is None or args.cpu not in affinity):
        parser.error("requested CPU is not available")
    if affinity:
        os.sched_setaffinity(0, {min(affinity) if args.cpu is None else args.cpu})
    directory = args.keep.resolve() if args.keep else Path(tempfile.mkdtemp(prefix="pystachy-match-"))
    output = args.json.resolve()
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(directory / "cache"), PYSTACHY_PROGRAM_CACHE="0",
               PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    source = HERE / "workload.py"
    executable = directory / "dispatch.exe"
    samples, loops, size = (1, 3, 257) if args.smoke else (args.samples, args.loops, args.size)
    report = {"schema_version": 1, "status": "incomplete", "cases": [],
              "measurement_kind": "correctness_only" if args.smoke else "paired_performance",
              "settings": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
              "effective_settings": {"samples": samples, "loops": loops, "size": size},
              "artifact_directory": str(directory) if args.keep else None,
              "scope": "Kernel timers exclude construction, validation and warm-up. Complete command wall_s includes these; JIT also includes compilation/startup. Ratios above 1 favor match."}
    try:
        if args.keep:
            directory.mkdir(parents=True, exist_ok=False)
        report["metadata"] = metadata(compiler, env, args.timeout)
        save(output, report)
        if "aot" in args.modes:
            report["aot_build"] = execute(compiler + ["build", str(source), "-o", str(executable)], env, args.timeout)
            report["aot_binary_bytes"] = executable.stat().st_size
            report["aot_binary_sha256"] = digest(executable)
        commands = {"cpython": [sys.executable, str(source)],
                    "jit": compiler + ["run", str(source)], "aot": [str(executable)]}
        for kind in args.kinds:
            for shape in args.shapes:
                case = {"kind": kind, "shape": shape, "oracle": {}, "warmups": {}, "measurements": {}}
                report["cases"].append(case)
                expected = None
                for variant in VARIANTS:
                    arguments = [kind, variant, shape, str(loops), str(size)]
                    oracle = checked(commands["cpython"] + arguments, env, args.timeout, loops * size, expected)
                    expected = oracle["checksum"]
                    case["oracle"][variant] = oracle
                # Validate every selected mode before recording timed pairs. This
                # also warms runtime caches, which are private to this controller.
                for mode in args.modes:
                    case["warmups"][mode] = {}
                    for variant in VARIANTS:
                        arguments = [kind, variant, shape, str(loops), str(size)]
                        case["warmups"][mode][variant] = checked(commands[mode] + arguments, env, args.timeout, loops * size, expected)
                    pairs = []
                    case["measurements"][mode] = {"pairs": pairs}
                    for sample in range(samples):
                        pair = {"order": list(VARIANTS[::1 if sample % 2 == 0 else -1])}
                        pairs.append(pair)
                        for variant in pair["order"]:
                            arguments = [kind, variant, shape, str(loops), str(size)]
                            pair[variant] = checked(commands[mode] + arguments, env, args.timeout, loops * size, expected)
                    if not args.smoke:
                        case["measurements"][mode]["summary"] = summaries(pairs)
                save(output, report)
                print(f"{kind}/{shape}: validated {', '.join(args.modes)}; {samples} paired sample(s)", flush=True)
        report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        save(output, report)
        if affinity:
            os.sched_setaffinity(0, affinity)
        if not args.keep:
            shutil.rmtree(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
