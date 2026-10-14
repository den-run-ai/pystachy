"""Run large supported CPython regex cases under CPython, native JIT and AOT.

usage: python3 tools/re_upstream_large.py [NATIVE_COMPILER] [--llvm LLVM_BIN]

The fixture stays outside tests/*.py: upstream's 50,000 repeats, 10,000 alternatives
and 10,000,000-character anchor subjects run with normal GC, not GC stress. The
CPython interpreter must match .python-version. Each phase has a generous timeout;
elapsed times are informational, with exact stdout/stderr and exit-status checks.
"""
import argparse
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tests" / "upstream" / "regex_large.py"
METHODS = ["test_stack_overflow", "test_bug_418626", "test_big_codesize",
           "test_search_anchor_at_beginning"]


class ProbeError(Exception):
    pass


def run(label: str, command: list[str], env: dict[str, str], timeout: float) -> bytes:
    start = time.monotonic()
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the process group too: a compiler may have an LLVM child running.
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise ProbeError(f"{label}: exceeded {timeout:g}s") from None
        if process.returncode != 0 or stderr:
            detail = (stdout + stderr).decode(errors="replace")
            raise ProbeError(f"{label}: exit {process.returncode}\n{detail}")
    print(f"re-upstream-large: {label} completed ({time.monotonic() - start:.2f}s)", flush=True)
    return stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler", nargs="?", default=str(ROOT / "pystachy"))
    parser.add_argument("--llvm", help="LLVM tool directory (instead of discovery through PATH)")
    parser.add_argument("--timeout", type=float, default=180,
                        help="maximum wall seconds per phase (default: 180)")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    want_version = (ROOT / ".python-version").read_text().strip()
    have_version = ".".join(str(x) for x in sys.version_info[:3])
    if sys.implementation.name != "cpython" or have_version != want_version:
        print(f"re-upstream-large: requires CPython {want_version}, got {sys.implementation.name} "
              f"{have_version}", file=sys.stderr)
        return 1
    # Do not inherit GC stress, disabled optimizations, other library paths or an alternate home.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYSTACHY_", "PYTHON"))}
    # A reused compiler may live in build/verify (or another checkout); test this tree's port.
    env["PYSTACHY_HOME"] = str(ROOT)
    if args.llvm:
        env["PYSTACHY_LLVM"] = str(Path(args.llvm).resolve())
    compiler = str(Path(args.compiler).resolve())
    try:
        oracle = run("CPython", [sys.executable, "-I", str(SOURCE)], env, args.timeout)
        completed = [line for line in oracle.splitlines() if line.startswith(b"PASS ")]
        expected = [f"PASS ReTests.{method}".encode() for method in METHODS]
        if completed != expected:
            raise ProbeError(f"CPython did not complete the expected methods: {completed!r}")
        with tempfile.TemporaryDirectory(prefix="pystachy-re-upstream-") as temporary:
            executable = str(Path(temporary) / "regex_large")
            jit = run("JIT", [compiler, "run", str(SOURCE)], env, args.timeout)
            if jit != oracle:
                raise ProbeError(f"JIT stdout differs from CPython:\n{jit!r}\nexpected:\n{oracle!r}")
            build = run("AOT build", [compiler, "build", str(SOURCE), "-o", executable], env, args.timeout)
            if build:
                raise ProbeError(f"AOT build wrote unexpected stdout: {build!r}")
            aot = run("AOT", [executable], env, args.timeout)
            if aot != oracle:
                raise ProbeError(f"AOT stdout differs from CPython:\n{aot!r}\nexpected:\n{oracle!r}")
    except (OSError, ProbeError) as error:
        print(f"re-upstream-large: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"re-upstream-large: {len(METHODS)} upstream methods agree under CPython, JIT and AOT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
