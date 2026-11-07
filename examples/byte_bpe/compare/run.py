"""Compare the byte-BPE port under a fixed, explicitly warmed process protocol.

Builds and checks run before timing. No packages are installed by this controller.
Every accepted sample must match the original CPython kernel's complete state.
"""
import argparse
import contextlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BENCH = ROOT / "bench/pyperformance"
spec = importlib.util.spec_from_file_location("byte_bpe_benchmark", HERE.parent / "benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
TIMINGS = ("first_train", "second_train", "train", "encode", "decode")
PRIMARY = ("cpython_original", "cpython_adapted", "cython_original", "cython_scalar",
           "cython_adapted", "mypyc_original", "pypy_original", "pystachy_aot",
           "pystachy_scalar_tuple")
SECONDARY = ("pystachy_jit", "pystachy_jit_inline100k", "pystachy_aot_gc8")


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"adapter expected exactly one occurrence of {old!r}")
    return source.replace(old, new)


def adapter(source, mode):
    """Apply only the changes identified in the recorded comparator experiment."""
    if mode == "cython_scalar":
        source = replace_once(source, "from __future__ import annotations\n",
                              "from __future__ import annotations\n\nimport cython\n")
        source = replace_once(source, "def bpe_encode(",
                              "@cython.locals(i=cython.Py_ssize_t, b=cython.uchar)\ndef bpe_encode(")
        source = replace_once(source, "def bpe_train(",
                              "@cython.locals(i=cython.Py_ssize_t, token=cython.Py_ssize_t)\ndef bpe_train(")
    elif mode == "mypyc_original":
        source = replace_once(source, "stats = collections.Counter()",
                              "stats: collections.Counter[tuple[bytes, bytes]] = collections.Counter()")
    elif mode == "pystachy_scalar_tuple":
        source = replace_once(source, "if (word[i], word[i + 1]) == most_common_pair:",
                              "if word[i] == most_common_pair[0] and word[i + 1] == most_common_pair[1]:")
    return source


def parse_times(stderr):
    rows = stderr.splitlines()
    if len(rows) != len(TIMINGS):
        raise ValueError("expected exactly five timing rows")
    result = {}
    for key, row in zip(TIMINGS, rows, strict=True):
        fields = row.split()
        if len(fields) != 2 or fields[0] != key:
            raise ValueError(f"invalid or duplicate timing row: {row!r}")
        value = float(fields[1])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"nonpositive or nonfinite timing: {row!r}")
        result[key] = value
    return result


def checked_sample(record, expected, encode_loops, decode_loops):
    if record["stdout"] != expected:
        raise ValueError("complete output differs from original CPython")
    times = parse_times(record["stderr"])
    for key in TIMINGS:
        divisor = encode_loops if key == "encode" else decode_loops if key == "decode" else 1
        record[key + "_seconds"] = times[key] / divisor
    del record["stdout"]
    return record


def fixture_output(text):
    # Python 3.11/PyPy and CPython 3.13 differ only in these tested ValueError texts.
    return text.replace("max() arg is an empty sequence", "max() iterable argument is empty").replace(
        "arg is an empty sequence", "max() iterable argument is empty")


def clean_env(llvm=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYSTACHY_", "PYPY"))
           and k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONINSPECT")}
    env.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYSTACHY_HOME=str(ROOT),
               PYSTACHY_PATH=str(BENCH), PYSTACHY_PROGRAM_CACHE="0")
    if llvm:
        env["PYSTACHY_LLVM"] = str(Path(llvm).resolve())
    return env


def executable(value):
    found = shutil.which(value)
    if not found:
        raise ValueError(f"executable not found: {value}")
    # Preserve a virtualenv's symlink path: resolving it selects the wrong packages.
    return os.path.abspath(found)


def build(command, env, directory, timeout):
    started = time.perf_counter()
    result = subprocess.Popen(command, cwd=directory, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = result.communicate(timeout=timeout)
    except BaseException:
        # setup.py and the native driver launch compilers. Bound the entire group,
        # so a timeout/interrupt cannot leave a compiler running after its parent.
        try:
            os.killpg(result.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        result.communicate()
        raise
    record = {"command": command, "cwd": str(directory), "wall_seconds": time.perf_counter() - started,
              "returncode": result.returncode, "stdout": stdout, "stderr": stderr}
    if result.returncode:
        raise RuntimeError(f"build failed ({result.returncode}): {command!r}\n{stderr[-3000:]}")
    return record


def build_extension(mode, directory, python, env, timeout):
    source = BENCH / "bpe_tokeniser.py" if mode == "cython_adapted" else HERE.parent / "upstream/bpe_tokeniser.py"
    (directory / "bpe_tokeniser.py").write_text(adapter(source.read_text(), mode))
    # Upstream's unused benchmark runner imports pyperf. Only its perf_counter is
    # needed at import; the common driver supplies all actual timing and warmups.
    (directory / "pyperf.py").write_text("from time import perf_counter\n")
    (directory / "pyperf.pyi").write_text(
        "from typing import Any\nfrom time import perf_counter as perf_counter\n"
        "class Runner:\n    metadata: dict[str, Any]\n"
        "    def bench_time_func(self, *args: Any, **kwargs: Any) -> Any: ...\n")
    if mode == "mypyc_original":
        setup = ('from setuptools import setup\nfrom mypyc.build import mypycify\n'
                 'setup(ext_modules=mypycify(["bpe_tokeniser.py", "--ignore-missing-imports"], opt_level="3"))\n')
    else:
        directives = {"language_level": 3}
        if mode == "cython_scalar":
            directives.update(overflowcheck=True, boundscheck=True, wraparound=True, initializedcheck=True)
        setup = ('from setuptools import setup, Extension\nfrom Cython.Build import cythonize\n'
                 'setup(ext_modules=cythonize([Extension("bpe_tokeniser", ["bpe_tokeniser.py"], '
                 f'extra_compile_args=["-O3"])], compiler_directives={directives!r}))\n')
    (directory / "setup.py").write_text(setup)
    return build([python, "setup.py", "build_ext", "--force", "--inplace"], env, directory, timeout)


def metadata_file(path):
    return {"path": str(path), "sha256": benchmark.digest(path), "bytes": path.stat().st_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="CPython with optional Cython/mypy build packages")
    parser.add_argument("--pypy", default="pypy3")
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--llvm", default=os.environ.get("PYSTACHY_LLVM"))
    parser.add_argument("--runtime-cache", type=Path, help="optional explicit runtime cache; binaries are always rebuilt")
    parser.add_argument("--modes", default=",".join(PRIMARY))
    parser.add_argument("--processes", type=benchmark.positive, default=5)
    parser.add_argument("--encode-loops", type=benchmark.positive, default=50)
    parser.add_argument("--decode-loops", type=benchmark.positive, default=200)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--smoke", action="store_true", help="small correctness workload; timings are not performance evidence")
    parser.add_argument("--work-dir", type=Path, help="retain fresh build inputs/artifacts in a new, nonexistent directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    selected = args.modes.split(",")
    if not selected or len(set(selected)) != len(selected) or any(m not in PRIMARY + SECONDARY for m in selected):
        parser.error("select unique, known comma-separated modes")
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not hasattr(os, "wait4"):
        parser.error("timeout must be positive and finite; a POSIX host with wait4 is required")
    if args.cpu is not None:
        if not hasattr(os, "sched_getaffinity") or args.cpu not in os.sched_getaffinity(0):
            parser.error("--cpu must be an available CPU on a host supporting affinity")
        os.sched_setaffinity(0, {args.cpu})
    if args.smoke:
        args.processes, args.encode_loops, args.decode_loops = 1, 1, 1
    report = {"status": "running", "smoke": args.smoke, "builds": {}, "checks": {}, "samples": {}, "order": []}
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temporary = args.output.with_name(args.output.name + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.output)

    save()
    try:
        python = executable(args.python)
        pypy = executable(args.pypy) if "pypy_original" in selected else None
        native = any(mode.startswith("pystachy_") for mode in selected)
        compiler = executable(args.compiler) if native else None
        env = clean_env(args.llvm)
        corpus = BENCH / "data/frankenstein_intro.txt"
        if benchmark.digest(corpus) != benchmark.CORPUS_SHA256:
            raise ValueError("corpus SHA-256 mismatch")
        original = benchmark.original_module()
        sources = [HERE / "run.py", HERE / "launch.py", HERE / "stages.py", HERE.parent / "benchmark.py",
                   HERE.parent / "upstream/bpe_tokeniser.py", BENCH / "bpe_tokeniser.py", corpus,
                   ROOT / "tests/programs/apps/byte_bpe.py"]
        report["input_sha256"] = {str(path.relative_to(ROOT)): benchmark.digest(path) for path in sources}
        report["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["git_revision"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report["git_status"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        report["platform"] = platform.platform()
        report["cpu_affinity"] = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
        report["cpu_model"] = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                    if line.startswith("model name")), None) if Path("/proc/cpuinfo").exists() else None
        report["load_average_start"] = os.getloadavg()
        report["versions"] = {"cpython": subprocess.check_output([python, "--version"], text=True).strip()}
        report["interpreters"] = {}
        for name, path, expected in (("cpython", python, "cpython"), ("pypy", pypy, "pypy")):
            if path:
                code = ("import json, sys; print(json.dumps({'implementation':sys.implementation.name, "
                        "'executable':sys.executable, 'version':sys.version, 'optimize':sys.flags.optimize}))")
                identity = json.loads(subprocess.check_output([path, "-c", code], env=env, text=True))
                if identity["implementation"] != expected or identity["optimize"] != 0:
                    raise ValueError(f"{name} mode requires {expected} with assertions enabled: {identity!r}")
                report["interpreters"][name] = identity
        if pypy:
            report["versions"]["pypy"] = subprocess.check_output([pypy, "--version"], text=True).strip()
        if any(mode.startswith(("cython_", "mypyc_")) for mode in selected):
            packages = ["setuptools"]
            if any(mode.startswith("cython_") for mode in selected):
                packages.append("Cython")
            if "mypyc_original" in selected:
                packages.append("mypy")
            code = ("import importlib.metadata as m, json, platform, sysconfig; "
                    f"print(json.dumps({{p:m.version(p) for p in {packages!r}}} | "
                    "{'python_compiler':platform.python_compiler(), 'CC':sysconfig.get_config_var('CC')}))")
            report["build_versions"] = json.loads(subprocess.check_output([python, "-c", code], env=env, text=True))
            cc = shlex.split(env.get("CC", report["build_versions"]["CC"]))
            report["build_versions"]["cc_version"] = subprocess.check_output(cc + ["--version"], env=env, text=True).strip()
        if args.work_dir:
            args.work_dir = args.work_dir.resolve()
            args.work_dir.mkdir(parents=True, exist_ok=False)
            workspace = contextlib.nullcontext(str(args.work_dir))
        else:
            workspace = tempfile.TemporaryDirectory(prefix="pystachy-byte-bpe-compare-")
        with workspace as temp:
            directory = Path(temp)
            env["PYSTACHY_CACHE"] = str(args.runtime_cache.resolve() if args.runtime_cache else directory / "runtime-cache")
            report["environment"] = {key: value for key, value in env.items()
                                     if key.startswith("PYSTACHY_") or key in ("PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE",
                                                                             "CC", "CXX", "CFLAGS", "CPPFLAGS", "LDFLAGS")}
            if native:
                report["native_provenance"] = benchmark.provenance([compiler], env, sources)
            original_dir = directory / "original"
            original_dir.mkdir()
            (original_dir / "bpe_tokeniser.py").write_text(original)
            fixture = directory / "correctness.py"
            fixture.write_text(replace_once((ROOT / "tests/programs/apps/byte_bpe.py").read_text(),
                'assert str(exc) == "max() iterable argument is empty"',
                'assert str(exc) in ["max() iterable argument is empty", "max() arg is an empty sequence", "arg is an empty sequence"]'))
            vocab_size = 1024
            if args.smoke:
                corpus = directory / "tiny.txt"
                corpus.write_text("banana bandana banana! 日本語 🦉\tÆ É Ġ\n" * 2)
                vocab_size = 264
            runargs = [str(corpus), str(vocab_size), str(args.encode_loops), str(args.decode_loops)]
            source = str(HERE / "stages.py")
            original_env = dict(env, PYTHONPATH=str(original_dir))
            report["checks"]["original_fixture"] = benchmark.run([python, str(fixture)], original_env, args.timeout)
            fixture_expected = fixture_output(report["checks"]["original_fixture"]["stdout"])
            oracle = benchmark.run([python, source, *runargs], original_env, args.timeout)
            parse_times(oracle["stderr"])
            expected = oracle["stdout"]
            if len(expected.splitlines()) != 4:
                raise ValueError("oracle must contain all four complete state rows")
            report["oracle"] = {"stdout": expected, "sha256": oracle["stdout_sha256"]}
            report["workload"] = {"corpus_bytes": corpus.stat().st_size, "corpus_sha256": benchmark.digest(corpus),
                                  "vocab_size": vocab_size, "processes": args.processes,
                                  "train_warmups": 2, "encode_warmups": 20, "decode_warmups": 100,
                                  "train_loops": 1, "encode_loops": args.encode_loops, "decode_loops": args.decode_loops}
            commands, environments, fixtures = {}, {}, {}
            artifacts = [original_dir / "bpe_tokeniser.py", fixture, corpus]
            native_executables = {}
            for mode in selected:
                runenv = dict(env)
                if mode in ("cpython_original", "pypy_original", "cpython_adapted"):
                    runenv["PYTHONPATH"] = str(BENCH if mode == "cpython_adapted" else original_dir)
                    interpreter = pypy if mode == "pypy_original" else python
                    commands[mode] = [interpreter, source, *runargs]
                    fixtures[mode] = [interpreter, str(fixture)]
                elif mode.startswith(("cython_", "mypyc_")):
                    module_dir = directory / mode
                    module_dir.mkdir()
                    report["builds"][mode] = build_extension(mode, module_dir, python, env, args.timeout)
                    extensions = list(module_dir.glob("*.so"))
                    if not extensions or not any(path.name.startswith("bpe_tokeniser.") for path in extensions):
                        raise RuntimeError(f"native extension missing after {mode} build")
                    artifacts.extend(extensions + [module_dir / name for name in ("bpe_tokeniser.py", "setup.py", "pyperf.py", "pyperf.pyi")])
                    prefix = [python, str(HERE / "launch.py"), str(module_dir)]
                    commands[mode], fixtures[mode] = prefix + [source, *runargs], prefix + [str(fixture)]
                else:
                    key = "scalar_tuple" if mode == "pystachy_scalar_tuple" else "default"
                    if key == "scalar_tuple":
                        module_dir = directory / key
                        module_dir.mkdir()
                        module = module_dir / "bpe_tokeniser.py"
                        module.write_text(adapter((BENCH / "bpe_tokeniser.py").read_text(), mode))
                        artifacts.append(module)
                        runenv["PYSTACHY_PATH"] = str(module_dir)
                    if key not in native_executables:
                        binary, checks = directory / (key + "-stages"), directory / (key + "-checks")
                        report["builds"][key + "_aot"] = build([compiler, "build", source, "-o", str(binary)], runenv, ROOT, args.timeout)
                        report["builds"][key + "_fixture"] = build([compiler, "build", str(fixture), "-o", str(checks)], runenv, ROOT, args.timeout)
                        artifacts.extend((binary, checks))
                        native_executables[key] = (binary, checks)
                    binary, checks = native_executables[key]
                    if mode == "pystachy_jit_inline100k":
                        runenv["PYSTACHY_JIT_INLINE"] = "100000"
                    if mode == "pystachy_aot_gc8":
                        runenv["PYSTACHY_GC_MIN"] = "8"
                    commands[mode] = ([compiler, "run", source] if mode.startswith("pystachy_jit") else [str(binary)]) + runargs
                    fixtures[mode] = [compiler, "run", str(fixture)] if mode.startswith("pystachy_jit") else [str(checks)]
                environments[mode] = runenv
                record = benchmark.run(fixtures[mode], runenv, args.timeout)
                if fixture_output(record["stdout"]) != fixture_expected:
                    raise ValueError(f"fixture differs from original CPython: {mode}")
                report["checks"][mode] = record
                if mode in ("pystachy_aot", "pystachy_scalar_tuple"):
                    stress = benchmark.run(fixtures[mode], dict(runenv, PYSTACHY_GC_STRESS="1"), args.timeout)
                    if fixture_output(stress["stdout"]) != fixture_expected:
                        raise ValueError(f"GC-stressed fixture differs: {mode}")
                    report["checks"][mode + "_gc_stress"] = stress
                save()
            report["artifacts"] = [metadata_file(path) for path in sorted(set(artifacts))]
            report["mode_environment_overrides"] = {
                mode: {key: value for key, value in runenv.items() if env.get(key) != value}
                for mode, runenv in environments.items()}
            report["rss_definition"] = "Linux main-process VmHWM after command installed; ~5ms sampling, includes warmups/launcher, excludes children"
            report["wall_definition"] = "whole warmed process including startup, I/O, imports, validation, and compiler where relevant; not single-query latency"
            report["samples"] = {mode: [] for mode in selected}
            for repeat in range(args.processes):
                order = selected[repeat % len(selected):] + selected[:repeat % len(selected)]
                if repeat % 2:
                    order.reverse()
                report["order"].append(order)
                for mode in order:
                    record = benchmark.run(commands[mode], environments[mode], args.timeout)
                    checked_sample(record, expected, args.encode_loops, args.decode_loops)
                    record.update(round=repeat, load_average_after=os.getloadavg())
                    report["samples"][mode].append(record)
                    save()
                    print(f"{repeat + 1}/{args.processes} {mode}: complete state matches", flush=True)
            metrics = [key + "_seconds" for key in TIMINGS] + ["wall_seconds", "cpu_seconds", "sampled_main_rss_kib"]
            report["summary"] = {mode: {metric: {"median": statistics.median(row[metric] for row in rows),
                                                "min": min(row[metric] for row in rows), "max": max(row[metric] for row in rows)}
                                        for metric in metrics if all(row.get(metric) is not None for row in rows)}
                                 for mode, rows in report["samples"].items()}
            for artifact in report["artifacts"]:
                if benchmark.digest(Path(artifact["path"])) != artifact["sha256"]:
                    raise ValueError(f"artifact changed during measurement: {artifact['path']}")
            if native:
                for path, digest in report["native_provenance"]["source_sha256"].items():
                    if benchmark.digest(ROOT / path) != digest:
                        raise ValueError(f"compiler source changed: {path}")
                if benchmark.digest(Path(compiler)) != report["native_provenance"]["compiler_binary_sha256"]:
                    raise ValueError("native compiler changed during measurement")
        for path, digest in report["input_sha256"].items():
            if benchmark.digest(ROOT / path) != digest:
                raise ValueError(f"source changed during measurement: {path}")
        report.update(status="passed", load_average_end=os.getloadavg())
        save()
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        save()
        raise
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
