"""Verify the pipe consumer reports completion before waiting for an earlier input."""

import argparse
import hashlib
import math
import os
from pathlib import Path
import platform
import selectors
import signal
import subprocess
import sys
import tempfile
import time

import check


def first_line(stream, timeout):
    """Do not let a readable but unterminated output line bypass the timeout."""
    deadline = time.monotonic() + timeout
    line = b""
    with selectors.DefaultSelector() as ready:
        ready.register(stream, selectors.EVENT_READ)
        while len(line) < 128:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not ready.select(remaining):
                raise RuntimeError(f"no complete pipe notification within {timeout}s: {line!r}")
            character = os.read(stream.fileno(), 1)
            line += character
            if not character or character == b"\n":
                return line
    raise RuntimeError("pipe notification exceeded its bounded line length")


def completion(command, env, directory, timeout):
    """Release the slow pipe only after observing the fast pipe's completion."""
    slow_read = slow_write = fast_read = fast_write = -1
    process = None
    try:
        slow_read, slow_write = os.pipe()
        fast_read, fast_write = os.pipe()
        assert os.write(fast_write, b"fast\x00") == 5
        os.close(fast_write)
        fast_write = -1
        args = command + ["5", "100", str(slow_read), str(fast_read)]
        process = subprocess.Popen(args, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                   pass_fds=(slow_read, fast_read), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        first = first_line(process.stdout, timeout)
        if first != b"done 1 6661737400\n":
            raise AssertionError(f"{command!r}: later pipe did not complete first: {first!r}")
        assert os.write(slow_write, b"slow\xff") == 5
        os.close(slow_write)
        slow_write = -1
        stdout, stderr = process.communicate(timeout=timeout)
        result = subprocess.CompletedProcess(args, process.returncode, first + stdout, stderr)
        if (result.returncode, result.stdout, result.stderr) != (0, b"done 1 6661737400\ndone 0 736c6f77ff\n", b""):
            raise AssertionError(check.detail("drain", args, timeout, result.returncode, result.stdout, result.stderr))
        return result
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        for fd in (slow_read, slow_write, fast_read, fast_write):
            if fd >= 0:
                os.close(fd)


def verify(args, report):
    pinned = (check.ROOT / ".python-version").read_text().strip()
    if platform.python_version() != pinned:
        raise RuntimeError(f"use pinned CPython {pinned}; running {platform.python_version()}")
    if sys.platform not in ("linux", "darwin"):
        raise RuntimeError("this prototype check supports Linux and macOS only")
    compiler = check.compiler_command(args.compiler)
    original = (check.HERE / "drain.py").read_bytes()
    checker_source = Path(__file__).read_bytes()
    before = check.hashes()
    report.update(python=pinned, platform=platform.platform(), compiler=compiler, source_sha256=before,
                  drain_sha256=hashlib.sha256(original).hexdigest(),
                  checker_sha256=hashlib.sha256(checker_source).hexdigest(), modes=[])
    with tempfile.TemporaryDirectory(prefix="pystachy-netio-drain-") as temporary:
        directory = Path(temporary)
        env = check.environment(directory)
        check.build_bridge(directory, env, check.c_compiler(args.cc, env), 60)
        source = directory / "drain.py"
        source.write_bytes(original)
        modes = [
            ("cpython_oracle", [sys.executable, str(source)], check.environment(directory, oracle=True)),
            ("cpython_bridge", [sys.executable, str(source)], env),
        ]
        if not args.cpython_only:
            executable = directory / "drain"
            check.quiet("drain/build", check.run("drain/build", compiler + ["build", str(source), "-o", str(executable)],
                                                env, check.ROOT, timeout=180))
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise ValueError("drain/build: compiler did not create a fresh executable")
            modes += [
                ("jit", compiler + ["run", str(source)], env),
                ("aot", [str(executable)], env),
                ("jit_gc", compiler + ["run", str(source)], env | {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
                ("aot_gc", [str(executable)], env | {"PYSTACHY_GC_STRESS": "1"}),
            ]
        reference = None
        for mode, command, child_env in modes:
            result = completion(command, child_env, directory, args.timeout)
            if reference is None:
                reference = result
            else:
                check.compare("drain/" + mode, result, reference)
            report["modes"].append(mode)
            print(f"{mode}: later pipe completion observed first; all binary output matches", flush=True)
    if (check.hashes() != before or (check.HERE / "drain.py").read_bytes() != original
            or Path(__file__).read_bytes() != checker_source):
        raise RuntimeError("prototype sources changed during drain validation; rerun on the final tree")
    expected = list(check.CPYTHON_MODES + (() if args.cpython_only else check.NATIVE_MODES))
    if report["modes"] != expected:
        raise RuntimeError("missing consumer validation modes")
    report["result"] = "pass"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(check.ROOT / "pystachy"), help="native or hosted compiler command")
    parser.add_argument("--cc", help="C11 compiler command; defaults to PYSTACHY_LLVM/clang or cc")
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=60, help="seconds for each bounded parent wait")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        parser.error("--timeout must be positive and finite")
    report = {"schema": 1, "result": "running", "scenario": "completion_order", "modes": []}
    check.write_report(args.json, report)
    try:
        verify(args, report)
    except Exception as error:
        report.update(result="fail", error=str(error))
        check.write_report(args.json, report)
        print(str(error), file=sys.stderr)
        return 1
    check.write_report(args.json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
