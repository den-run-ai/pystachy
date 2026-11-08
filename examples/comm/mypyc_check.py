"""Optional mypyc interoperability check; requires mypyc and setuptools.

The ordinary mode compiles unmodified consumers and imports the CPython wrapper.
The split mode keeps annotation-inspecting extern declarations in Python and
compiles the remaining wrapper, without changing the checked-in source.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from check import oracle_output


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONSUMERS = ("exercise", "record_worker", "bench_workload", "compatibility_probe")


def run(command, cwd, env, timeout=180):
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=5)
        raise
    return {"returncode": process.returncode, "stdout": stdout.decode(),
            "stderr": stderr.decode(), "seconds": time.perf_counter() - started}


def require_ok(result):
    if result["returncode"]:
        raise RuntimeError(result["stdout"][-8000:] + result["stderr"][-8000:])


def prepare(directory):
    directory.mkdir()
    for module in ("comm", *CONSUMERS):
        shutil.copyfile(HERE / (module + ".py"), directory / (module + ".py"))
    # ffi's marker classes describe C types, not nominal Python subclasses at
    # call sites. Leave this one dynamic module untyped; do not ignore errors in
    # the consumers or compile the runtime-introspecting CPython FFI twin.
    (directory / "mypy.ini").write_text(
        "[mypy]\nfollow_imports = silent\n[mypy-ffi]\nignore_missing_imports = True\n")


def build(directory, modules, env, allow_empty_extern=False):
    command = [sys.executable, "-m", "mypyc", "--config-file=mypy.ini"]
    if allow_empty_extern:
        # Ellipsis bodies are replaced by @extern; mypy's empty-body diagnostic
        # otherwise stops before testing mypyc's runtime annotation behavior.
        with (directory / "mypy.ini").open("a") as config:
            config.write("[mypy-comm]\ndisable_error_code = empty-body\n")
    command.extend(name + ".py" for name in modules)
    result = run(command, directory, env)
    (directory / "build.log").write_text(result["stdout"] + result["stderr"])
    require_ok(result)
    return result["seconds"]


def verify(directory, compiled, env):
    code = """
import importlib, importlib.machinery, json, sys
names = sys.argv[1:]
origins = {name: importlib.import_module(name).__file__ for name in names}
assert all(any(path.endswith(suffix) for suffix in importlib.machinery.EXTENSION_SUFFIXES)
           for path in origins.values()), origins
print(json.dumps(origins, sort_keys=True))
"""
    result = run([sys.executable, "-c", code, *compiled], directory, env)
    require_ok(result)
    origins = json.loads(result["stdout"])
    result = run([sys.executable, "-c", "import exercise; exercise.main()"], directory, env)
    require_ok(result)
    if result["stdout"].encode() != oracle_output(8):
        raise AssertionError("mypyc exercise differs from independent Python oracle")
    result = run([sys.executable, "-c", "import compatibility_probe; compatibility_probe.main()"],
                 directory, env)
    require_ok(result)
    expected = ("source-order sums 0.0 1.0\nnonfinite IEEE results\n"
                "signed tag limits, failed-submit atomicity, cancellation leases\n")
    if result["stdout"] != expected:
        raise AssertionError("mypyc compatibility probe differs from its contract")
    # Include the actual application helper and numerical workload, rather than
    # accepting import success as evidence of executing the feature.
    code = """
from bench_workload import records, reductions
assert records(7, 256) == 1792
assert records(3, 0) == 0
assert reductions(7, 33) == 3.5
assert reductions(3, 0) == 0.0
print('record and reduction consumers pass')
"""
    result = run([sys.executable, "-c", code], directory, env)
    require_ok(result)
    # Keep stdin open while awaiting each acknowledgment.  An EOF-only test
    # misses readers that block by peeking past a complete newline record.
    code = """
import os, select, subprocess, sys, time
worker = subprocess.Popen([sys.executable, '-c', 'import record_worker; record_worker.main()'],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    for record in (b'{"job":1}\\n', b'{"job":2}\\n'):
        worker.stdin.write(record)
        worker.stdin.flush()
        result = b''
        deadline = time.monotonic() + 5
        while not result.endswith(b'\\n'):
            remaining = deadline - time.monotonic()
            assert remaining > 0 and select.select([worker.stdout], [], [], remaining)[0]
            part = os.read(worker.stdout.fileno(), 4096)
            assert part
            result += part
        assert result == record
    worker.stdin.close()
    worker.stdin = None
    stdout, stderr = worker.communicate(timeout=5)
    assert worker.returncode == 0 and stdout == stderr == b''
finally:
    if worker.poll() is None:
        worker.kill()
        worker.wait(timeout=5)
"""
    result = run([sys.executable, "-c", code], directory, env, timeout=30)
    require_ok(result)
    return origins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True,
                        help="new, retained directory for extensions and JSON report")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--split-wrapper", action="store_true")
    parser.add_argument("--probe-unchanged-wrapper", action="store_true")
    args = parser.parse_args()
    directory = args.build_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "tools" / "rt_cpython") + os.pathsep + env.get("PYTHONPATH", "")
    env["LD_LIBRARY_PATH"] = str(directory) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    source_paths = [HERE / (name + ".py") for name in ("comm", *CONSUMERS)]
    source_paths += [HERE / "bridge.c", HERE / "bridge.h", HERE / "check.py", Path(__file__),
                     ROOT / "tools" / "rt_cpython" / "ffi.py"]
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source_paths}
    report = {"python": sys.version, "sources": hashes,
              "ffi_runtime": "interpreted tools/rt_cpython/ffi.py",
              "optimization": "mypyc default -O3; assertions retained"}
    result = run([sys.executable, "-c", "from mypy.version import __version__; print(__version__)"],
                 directory, env)
    require_ok(result)
    report["mypyc"] = result["stdout"].strip()
    result = run([args.cc, "-std=c11", "-O2", "-fPIC", "-shared", str(HERE / "bridge.c"),
                  "-o", str(directory / "libpystachy_comm.so")], directory, env)
    require_ok(result)
    consumer = directory / "consumer"
    prepare(consumer)
    seconds = build(consumer, CONSUMERS, env)
    report["consumer"] = {"build_seconds": seconds,
                          "compiled_origins": verify(consumer, CONSUMERS, env),
                          "wrapper": str(consumer / "comm.py")}
    if args.probe_unchanged_wrapper:
        original = directory / "unchanged"
        prepare(original)
        seconds = build(original, ("comm", *CONSUMERS), env, allow_empty_extern=True)
        result = run([sys.executable, "-c", "import comm"], original, env)
        report["unchanged_wrapper"] = {"build_seconds": seconds, **result}
        if result["returncode"] == 0:
            report["unchanged_wrapper"]["compiled_origins"] = verify(
                original, ("comm", *CONSUMERS), env)
    if args.split_wrapper:
        split = directory / "split"
        prepare(split)
        source = (split / "comm.py").read_text()
        start, end = source.index("@extern("), source.index("def _checked(")
        declarations = source[start:end]
        names = [node.name for node in ast.parse(declarations).body
                 if isinstance(node, ast.FunctionDef)]
        (split / "comm_ffi.py").write_text(
            "from ffi import c_int, c_int64, c_size_t, c_void_p, extern\n\n" + declarations)
        (split / "comm.py").write_text(source[:start] + "from comm_ffi import "
                                       + ", ".join(names) + "\n\n\n" + source[end:])
        seconds = build(split, ("comm", *CONSUMERS), env)
        report["split_wrapper"] = {"build_seconds": seconds,
                                  "compiled_origins": verify(split, ("comm", *CONSUMERS), env),
                                  "interpreted_declarations": str(split / "comm_ffi.py")}
    after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in source_paths}
    if hashes != after:
        raise RuntimeError("consumed sources changed while checking mypyc")
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
