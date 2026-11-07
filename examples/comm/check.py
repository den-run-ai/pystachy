"""Build and validate the optional local buffer/completion reference backend."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(command, env, timeout=180):
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, stderr = process.communicate(timeout=5)
        if isinstance(error, subprocess.TimeoutExpired):
            raise RuntimeError(f"{shlex.join(command)} timed out after {timeout}s\n"
                               + stderr.decode("utf-8", "replace")[-8000:]) from error
        raise
    if process.returncode or stderr:
        raise RuntimeError(f"{shlex.join(command)} exited {process.returncode}\n"
                           + stderr.decode("utf-8", "replace")[-8000:])
    return stdout


def ordered_column_sums(ranks):
    # The prototype specifies source-list order, whereas CPython's sum(float)
    # may use compensated accumulation. Match the API's individual IEEE adds.
    reduced = []
    for column in range(len(ranks[0])):
        total = 0.0
        for row in ranks:
            total += row[column]
        reduced.append(total)
    return reduced


def oracle_output(repeat):
    """Independent Python arithmetic/byte oracle; never imports the bridge."""
    ranks = [[float(rank + 1), float(rank * rank), -float(rank)] for rank in range(4)]
    reduced = ordered_column_sums(ranks)
    gathered = [value for row in ranks for value in row]
    lines = [
        f"allreduce {reduced}",
        f"allgather {gathered}",
        f"broadcast {bytes([0, 255, 65, 0, 66])!r}",
        f"byte allgather {bytes([97, 0, 255, 66])!r}",
        f"owned buffers, nested views, zero lengths {repeat}",
        "leases, terminal capacity, stale IDs",
        "cancellation, completion order, no canceled writes",
        "bounds, overlap, dtype, shape, context validation",
        f"pending shutdown and idempotent close {repeat}",
    ]
    return ("\n".join(lines) + "\n").encode()


def compare_output(name, actual, expected):
    if actual != expected:
        raise AssertionError(f"{name} differs from the independent oracle\n"
                             f"actual: {actual!r}\nexpected: {expected!r}")


def source_hashes():
    paths = [HERE / name for name in ["bridge.c", "bridge.h", "comm.py", "exercise.py",
                                     "ownership.c", "check.py"]]
    paths += [ROOT / "tools" / "rt_cpython" / "ffi.py"]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def verify_sources(before, report):
    after = source_hashes()
    report["sources_after"] = after
    if before != after:
        raise RuntimeError("consumed sources changed during the check; rerun from a fixed tree")


HOSTED_PROBE = '''
import threading
import comm
with comm.Context(capacity=1) as ctx:
    source = ctx.from_bytes(b"retained")
    dest = ctx.buffer("u8", 8)
    errors = []
    def foreign_thread():
        try:
            ctx.progress()
        except RuntimeError:
            errors.append("owner")
    worker = threading.Thread(target=foreign_thread)
    worker.start()
    worker.join(3)
    assert not worker.is_alive() and errors == ["owner"]
    request = ctx.copy(source, dest)
    ctx.progress()
    original = comm.Completion
    def reenter_completion(*args):
        try:
            ctx.close()
        except RuntimeError:
            errors.append("reentrant")
        else:
            raise AssertionError("reentrant close was accepted")
        return original(*args)
    comm.Completion = reenter_completion
    try:
        assert ctx.peek().request_id == request
    finally:
        comm.Completion = original
    assert errors == ["owner", "reentrant"]
    def fail_completion(*args):
        raise MemoryError("injected completion conversion failure")
    comm.Completion = fail_completion
    try:
        try:
            ctx.poll()
        except MemoryError:
            pass
        else:
            raise AssertionError("injected completion failure was not observed")
    finally:
        comm.Completion = original
    assert ctx.test(request)
    event = ctx.peek()
    assert event.request_id == request and event.status == 0
    assert ctx.peek().request_id == request
    ctx.ack(request)
    assert dest.to_bytes() == b"retained" and ctx.poll() == []
ctx = comm.Context()
source = ctx.from_bytes(b"x")
dest = ctx.buffer("u8", 1)
ctx.copy(source, dest)
original_close = comm.cc_close
calls = []
def close_then_interrupt(handle):
    original_close(handle)
    calls.append("freed")
    raise KeyboardInterrupt("injected signal after free")
comm.cc_close = close_then_interrupt
try:
    try:
        ctx.close()
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("injected post-free signal was not observed")
    ctx.close()
finally:
    comm.cc_close = original_close
assert calls == ["freed"]
try:
    ctx.progress()
except ValueError:
    pass
else:
    raise AssertionError("freed context remained callable")
ctx = comm.Context()
source = ctx.from_bytes(b"x")
original_open = comm.Context._open
def open_then_interrupt(self):
    original_open(self)
    raise KeyboardInterrupt("injected signal after open")
comm.Context._open = open_then_interrupt
try:
    for action in [ctx.progress, source.to_bytes, lambda: source.view(0, 1),
                   lambda: ctx.buffer("u8", 1)]:
        try:
            action()
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("injected post-open signal was not observed")
        assert ctx._busy is False
finally:
    comm.Context._open = original_open
assert source.to_bytes() == b"x"
ctx.close()

original_buffer = comm.Buffer
def fail_buffer(*args):
    raise MemoryError("injected buffer constructor failure")
with comm.Context(byte_limit=1) as ctx:
    comm.Buffer = fail_buffer
    try:
        for _ in range(160):
            try:
                ctx.buffer("u8", 1)
            except MemoryError:
                pass
            else:
                raise AssertionError("buffer constructor failure was not observed")
    finally:
        comm.Buffer = original_buffer
    # Both the 128-entry descriptor table and one-byte payload quota must be free.
    source = ctx.from_bytes(b"x")
    comm.Buffer = fail_buffer
    try:
        for _ in range(160):
            try:
                source.view(0, 1)
            except MemoryError:
                pass
            else:
                raise AssertionError("view constructor failure was not observed")
    finally:
        comm.Buffer = original_buffer
    assert source.to_bytes() == b"x"
    source.close()
    # Leaked view references would retain the original byte and reject this.
    replacement = ctx.from_bytes(b"y")
    assert replacement.to_bytes() == b"y"
print("hosted ownership, reentrancy, completion retry, signals and constructor cleanup passed")
'''


def check(args, report):
    if sys.platform != "linux":
        raise ValueError("this example's build harness currently targets Linux")
    if args.leak_check and not args.sanitizers:
        raise ValueError("--leak-check requires --sanitizers")
    if not 1 <= args.repeat <= 64:
        raise ValueError("--repeat must be between 1 and 64")
    before = source_hashes()
    report["sources_before"] = before
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE"}}
    env["PYSTACHY_HOME"] = str(ROOT)
    env["PYSTACHY_PATH"] = str(HERE)
    env["PYTHONPATH"] = str(ROOT / "tools" / "rt_cpython") + os.pathsep + str(HERE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    common = shlex.split(args.cc) + ["-std=c11", "-Wall", "-Wextra", "-Werror", "-g"]
    compiler = shlex.split(args.compiler)
    report.update({
        "platform": platform.platform(), "python": sys.version,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "repeat": args.repeat, "runs": {},
        "cc_version": subprocess.check_output(shlex.split(args.cc) + ["--version"], text=True).splitlines()[0],
        "compiler_command": None if args.cpython_only else compiler,
    })
    if not args.cpython_only:
        candidate = ROOT / compiler[0]
        compiler_file = candidate if candidate.is_file() else Path(shutil.which(compiler[0]) or compiler[0])
        if compiler_file.is_file():
            report["compiler_sha256"] = hashlib.sha256(compiler_file.read_bytes()).hexdigest()
    expected = oracle_output(args.repeat)
    with tempfile.TemporaryDirectory(prefix="pystachy-comm-") as directory:
        build = Path(directory)
        library = build / "libpystachy_comm.so"
        run(common + ["-O2", "-shared", "-fPIC", str(HERE / "bridge.c"), "-o", str(library)], env)
        report["bridge_sha256"] = hashlib.sha256(library.read_bytes()).hexdigest()
        env["LD_LIBRARY_PATH"] = str(build) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        env["PYSTACHY_CACHE"] = str(build / "cache")
        executable = build / "exercise"
        commands = [("cpython", [sys.executable, str(HERE / "exercise.py")], {})]
        if not args.cpython_only:
            run(compiler + ["build", str(HERE / "exercise.py"), "-o", str(executable)], env)
            commands += [
                ("jit", compiler + ["run", str(HERE / "exercise.py")], {}),
                ("aot", [str(executable)], {}),
                ("jit_gc", compiler + ["run", str(HERE / "exercise.py")], {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
                ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": "1"}),
            ]
        for name, command, settings in commands:
            actual = run(command + [str(args.repeat)], env | settings)
            compare_output(name, actual, expected)
            report["runs"][name] = {"stdout_sha256": hashlib.sha256(actual).hexdigest(), "gc": settings}
            print(f"{name}: collectives, leases, cancellation, bounds and cleanup passed", flush=True)
        output = run([sys.executable, "-c", HOSTED_PROBE], env)
        print(output.decode().strip(), flush=True)
        report["runs"]["hosted_lifetime"] = {"stdout_sha256": hashlib.sha256(output).hexdigest()}
        probe = build / "ownership"
        instrument = ["-O1", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"] if args.sanitizers else ["-O2"]
        run(common + instrument + [str(HERE / "ownership.c"), str(HERE / "bridge.c"), "-o", str(probe)], env)
        output = run([str(probe)], env | {"ASAN_OPTIONS": f"detect_leaks={int(args.leak_check)}:halt_on_error=1",
                                       "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
        print(output.decode().strip(), flush=True)
        report["runs"]["ownership"] = {"sanitizers": args.sanitizers, "leak_check": args.leak_check,
                                         "stdout_sha256": hashlib.sha256(output).hexdigest()}
    verify_sources(before, report)
    print("Local CPU reference backend only; no network or device-backend validation", flush=True)


def write_report(path, report):
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--repeat", type=int, default=8)
    parser.add_argument("--sanitizers", action="store_true", help="ASan/UBSan for standalone C probe")
    parser.add_argument("--leak-check", action="store_true", help="enable LSan where the process environment supports it")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = {"result": "running", "runs": {}}
    write_report(args.report, report)
    try:
        check(args, report)
    except Exception as error:
        report["result"] = "fail"
        report["error"] = str(error)
        write_report(args.report, report)
        print(f"comm check failed: {error}", file=sys.stderr)
        return 1
    report["result"] = "pass"
    write_report(args.report, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
