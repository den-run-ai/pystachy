"""Collect real compiler IR and diagnostics through the optional native pipe drain.

The host owns compiler processes, exit statuses and cleanup. The unchanged
drain.py owns inherited read descriptors. Every mode is checked byte-for-byte
against separate, serial CPython-hosted compiler jobs captured with stdlib I/O.
End-to-end timings include compiler work, consumer startup and hex encoding;
they are not isolated I/O throughput or a compiler speedup claim.

The current JIT driver overwrites descriptors 7--9 for its own artifacts. This
launcher explicitly duplicates inherited pipes to 64+ and reports the mapping;
it does not fix or claim compatibility for those reserved low descriptors.
"""

import argparse
import fcntl
import hashlib
import math
import os
from pathlib import Path
import platform
import resource
import selectors
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

import check

INPUTS = (
    ("hello", "tests/programs/apps/ouro2_hello.py", 0),
    ("containers", "tests/programs/containers/dicts.py", 0),
    ("diagnostic", "tests/errors/syntax/syntax_await_module.py", 1),
)
MAXIMUM = 16777216
FIRST_INHERITED_FD = 64


class Cancelled(RuntimeError):
    """Not InterruptedError: selectors catches that type as a retryable syscall EINTR."""


def cleanup(processes):
    """Kill all owned process groups before reaping, including after launch failure."""
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in processes:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        process.wait(timeout=5)


class Owned:
    """Main-thread scope for directly launched process groups, not a worker scheduler."""

    def __init__(self):
        self.processes = []
        self.fds = []
        self.launching = False
        self.stopping = False
        self.cancelled = 0

    def __enter__(self):
        self.handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        for signum in self.handlers:
            signal.signal(signum, self.interrupt)
        return self

    def interrupt(self, signum, frame):
        self.cancelled = signum
        if not self.launching and not self.stopping:
            raise Cancelled(f"compiler collection cancelled by signal {signum}")

    def start(self, command, env, directory, pass_fds=()):
        # A signal between Popen's fork and our ownership record must not lose the child.
        self.launching = True
        try:
            process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True, pass_fds=pass_fds)
            self.processes.append(process)
        finally:
            self.launching = False
        if self.cancelled:
            raise Cancelled(f"compiler collection cancelled by signal {self.cancelled}")
        return process

    def duplicate(self, fd):
        # Match start's signal protection between acquiring and recording ownership.
        self.launching = True
        try:
            duplicate = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, FIRST_INHERITED_FD)
            self.fds.append(duplicate)
        finally:
            self.launching = False
        if self.cancelled:
            raise Cancelled(f"compiler collection cancelled by signal {self.cancelled}")
        return duplicate

    def __exit__(self, kind, value, traceback):
        self.stopping = True
        try:
            cleanup(self.processes)
        finally:
            try:
                for fd in self.fds:
                    os.close(fd)
            finally:
                for signum, handler in self.handlers.items():
                    signal.signal(signum, handler)
        if self.cancelled and kind is None:
            raise Cancelled(f"compiler collection cancelled by signal {self.cancelled}")


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("compiler pipe collection deadline expired")
    return seconds


def serial(command, env, directory, timeout, maximum, pass_fds=()):
    """Independent bounded stdlib capture, retaining deliberate compiler failures."""
    started = time.monotonic()
    deadline = started + timeout
    buffers = [bytearray(), bytearray()]
    with Owned() as owned:
        process = owned.start(command, env, directory, pass_fds)
        with selectors.DefaultSelector() as ready:
            for index, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False)
                ready.register(stream, selectors.EVENT_READ, index)
            while ready.get_map():
                for key, events in ready.select(remaining(deadline)):
                    data = os.read(key.fd, min(65536, maximum - len(buffers[key.data]) + 1))
                    if not data:
                        ready.unregister(key.fileobj)
                    else:
                        buffers[key.data].extend(data)
                        if len(buffers[key.data]) > maximum:
                            raise ValueError("serial compiler output exceeds configured bound")
        status = process.wait(timeout=remaining(deadline))
        return subprocess.CompletedProcess(command, status, bytes(buffers[0]), bytes(buffers[1])), time.monotonic() - started


def parse_output(output, streams, maximum):
    """Require one canonical, bounded completion for every inherited stream."""
    if not output.endswith(b"\n") or len(output) > streams * (2 * maximum + 32):
        raise ValueError("incomplete or oversized drain output")
    found = {}
    order = []
    for line in output[:-1].split(b"\n"):
        fields = line.split(b" ", 2)
        if len(fields) != 3 or fields[0] != b"done":
            raise ValueError("malformed drain completion")
        try:
            index = int(fields[1])
            data = bytes.fromhex(fields[2].decode("ascii"))
        except (ValueError, UnicodeError) as error:
            raise ValueError("malformed drain completion") from error
        if (str(index).encode() != fields[1] or index < 0 or index >= streams or index in found
                or data.hex().encode() != fields[2] or len(data) > maximum):
            raise ValueError("invalid, duplicate or oversized drain completion")
        found[index] = data
        order.append(index)
    if len(found) != streams:
        raise ValueError("missing drain completions")
    return [found[index] for index in range(streams)], order


def run(label, command, env, cwd, *, timeout=30, pass_fds=()):
    """check.run-compatible build runner with owned signal/launch cleanup and bounded logs."""
    result, _ = serial(command, env, cwd, timeout, MAXIMUM, pass_fds)
    if result.returncode:
        raise RuntimeError(check.detail(label, command, timeout, result.returncode, result.stdout, result.stderr))
    return result


def collect(commands, consumer, worker_env, consumer_env, directory, timeout, maximum):
    """Run identical compiler jobs concurrently; only the collector changes by mode."""
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    deadline = started + timeout
    fds = []
    mapping = []
    with Owned() as owned:
        for index, command in enumerate(commands):
            process = owned.start(command, worker_env, directory)
            for channel, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                fd = owned.duplicate(stream.fileno())
                fds.append(fd)
                mapping.append({"job": index, "channel": channel, "original_fd": stream.fileno(), "passed_fd": fd})
        command = consumer + [str(timeout), str(maximum), *map(str, fds)]
        result, _ = serial(command, consumer_env, directory, remaining(deadline),
                           len(fds) * (2 * maximum + 32), tuple(fds))
        if result.returncode:
            raise RuntimeError(check.detail("compiler/drain", command, timeout, result.returncode,
                                            result.stdout, result.stderr))
        if result.stderr:
            raise ValueError("drain produced unexpected diagnostics: " + repr(result.stderr))
        data, order = parse_output(result.stdout, len(fds), maximum)
        results = [subprocess.CompletedProcess(command, process.wait(timeout=remaining(deadline)), data[2 * index],
                                               data[2 * index + 1])
                   for index, (command, process) in enumerate(zip(commands, owned.processes, strict=True))]
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return results, {"end_to_end_s": time.monotonic() - started,
                         "children_cpu_s": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                         "completion_order": order, "descriptor_mapping": mapping}


def witness(result):
    return {"exit_code": result.returncode,
            "stdout_bytes": len(result.stdout), "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_bytes": len(result.stderr), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}


def compare(name, actual, expected):
    if (actual.returncode, actual.stdout, actual.stderr) != (expected.returncode, expected.stdout, expected.stderr):
        raise ValueError(f"{name}: differs from serial CPython-hosted compiler; "
                         f"expected={witness(expected)!r}; actual={witness(actual)!r}")


def sources():
    paths = [check.ROOT / name for name in ("VERSION", ".python-version")]
    for pattern in ("*.py", "*.c", "*.h"):
        paths.extend(check.ROOT.glob(pattern))
    for name in ("src", "lib", "tools/rt_cpython"):
        paths.extend((check.ROOT / name).rglob("*.py"))
    for name in ("ryu", "mpz"):
        paths.extend(path for path in (check.ROOT / name).rglob("*") if path.suffix in (".c", ".h"))
    paths += [check.HERE / name for name in (*check.SOURCES, "drain.py", "compiler_dogfood.py")]
    paths += [check.ROOT / path for name, path, status in INPUTS]
    return {str(path.relative_to(check.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths))}


def artifacts(command):
    paths = []
    for index, word in enumerate(command):
        path = Path(shutil.which(word) or word) if index == 0 else Path(word)
        if path.is_file():
            paths.append(path.resolve())
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def verify(args, report):
    pinned = (check.ROOT / ".python-version").read_text().strip()
    if sys.implementation.name != "cpython" or platform.python_version() != pinned:
        raise RuntimeError(f"use pinned CPython {pinned}; running {sys.implementation.name} {platform.python_version()}")
    if sys.platform not in ("linux", "darwin"):
        raise RuntimeError("compiler pipe dogfood supports Linux and macOS only")
    compiler = check.compiler_command(args.compiler)
    hosted = [sys.executable, str(check.ROOT / "pystachy.py")]
    before = sources()
    binaries = artifacts(compiler + hosted)
    inputs = [{"name": name, "path": str(check.ROOT / path), "expected_exit_code": status}
              for name, path, status in INPUTS]
    commands = [compiler + ["ir", item["path"]] for item in inputs]
    report.update(python=pinned, platform=platform.platform(), compiler=compiler,
                  compiler_artifacts_sha256=binaries, source_sha256=before, inputs=inputs,
                  worker_commands=commands, timeout_s=args.timeout, maximum_bytes_per_stream=args.maximum,
                  descriptor_policy={"first_passed_fd": FIRST_INHERITED_FD,
                                     "reason": "Work around current JIT driver overwriting inherited descriptors 7--9. "
                                               "Low-descriptor compatibility remains a compiler bug outside this example."},
                  samples=args.samples, builds={}, reference={}, runs={}, modes=[],
                  timing_scope="End-to-end: unchanged compiler jobs, collector startup, buffering and hex encoding. "
                               "The AOT collector build is separate; JIT timings include compilation. "
                               "Serial reference timings use the CPython-hosted compiler and are not a speedup baseline.")
    with tempfile.TemporaryDirectory(prefix="pystachy-netio-compiler-") as temporary:
        directory = Path(temporary)
        env = check.environment(directory)
        started = time.monotonic()
        bridge = check.build_bridge(directory, env, check.c_compiler(args.cc, env), args.build_timeout, runner=run)
        report["builds"]["bridge_s"] = time.monotonic() - started
        report["builds"]["bridge_sha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
        source = directory / "drain.py"
        source.write_bytes((check.HERE / "drain.py").read_bytes())
        modes = [
            ("cpython_oracle", [sys.executable, str(source)], check.environment(directory, oracle=True)),
            ("cpython_bridge", [sys.executable, str(source)], env),
        ]
        if not args.cpython_only:
            executable = directory / "drain"
            started = time.monotonic()
            check.quiet("drain/build", run("drain/build", compiler + ["build", str(source), "-o", str(executable)],
                                           env, check.ROOT, timeout=args.build_timeout))
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise ValueError("drain/build: compiler did not create a fresh executable")
            report["builds"].update(consumer_aot_s=time.monotonic() - started,
                                   consumer_aot_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
            modes += [("jit", compiler + ["run", str(source)], env), ("aot", [str(executable)], env),
                      ("jit_gc", compiler + ["run", str(source)], env | {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
                      ("aot_gc", [str(executable)], env | {"PYSTACHY_GC_STRESS": "1"})]
        references = []
        for item in inputs:
            command = hosted + ["ir", item["path"]]
            result, wall = serial(command, env, directory, args.timeout, args.maximum)
            if result.returncode != item["expected_exit_code"]:
                raise ValueError(f"unexpected serial compiler status for {item['name']}: {witness(result)!r}")
            if ((result.returncode == 0 and (not result.stdout or result.stderr))
                    or (result.returncode != 0 and (result.stdout or not result.stderr))):
                raise ValueError(f"missing IR or deliberate diagnostic for {item['name']}")
            references.append(result)
            report["reference"][item["name"]] = witness(result) | {"command": command, "wall_s": wall}
        report["modes"] = [name for name, command, child_env in modes]
        report["runs"] = {name: [] for name in report["modes"]}
        for sample in range(args.samples):
            offset = sample % len(modes)
            for mode, command, child_env in modes[offset:] + modes[:offset]:
                actual, timings = collect(commands, command, env, child_env, directory, args.timeout, args.maximum)
                for item, result, reference in zip(inputs, actual, references, strict=True):
                    compare(mode + "/" + item["name"], result, reference)
                report["runs"][mode].append(timings | {"sample": sample,
                                                       "workers": [witness(result) for result in actual]})
                check.write_report(args.json, report)
                print(f"{mode}: sample {sample + 1}: IR, diagnostics and exit statuses match "
                      f"({timings['end_to_end_s']:.3f}s end-to-end)", flush=True)
    if sources() != before or artifacts(compiler + hosted) != binaries:
        raise RuntimeError("consumed compiler/dogfood sources or executables changed; rerun on the final tree")
    expected = list(check.CPYTHON_MODES + (() if args.cpython_only else check.NATIVE_MODES))
    if report["modes"] != expected or any(len(rows) != args.samples for rows in report["runs"].values()):
        raise RuntimeError("missing compiler collection validation modes or samples")
    report["median_end_to_end_s"] = {mode: statistics.median(row["end_to_end_s"] for row in rows)
                                     for mode, rows in report["runs"].items()}
    report["result"] = "pass"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(check.ROOT / "pystachy"), help="native or hosted compiler command")
    parser.add_argument("--cc", help="C11 compiler command; defaults to PYSTACHY_LLVM/clang or cc")
    parser.add_argument("--cpython-only", action="store_true", help="run only the two CPython collectors")
    parser.add_argument("--samples", type=int, default=1, help="rotated repetitions of each collector (default: 1)")
    parser.add_argument("--timeout", type=float, default=60, help="overall deadline per compiler batch")
    parser.add_argument("--build-timeout", type=float, default=180)
    parser.add_argument("--maximum", type=int, default=1048576, help="bytes per stdout/stderr stream (default: 1 MiB)")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if (args.samples < 1 or not 1 <= args.maximum <= MAXIMUM or args.timeout <= 0 or args.build_timeout <= 0
            or not math.isfinite(args.timeout) or not math.isfinite(args.build_timeout)):
        parser.error("positive samples, finite positive deadlines and a 1..16777216 byte bound are required")
    report = {"schema": 1, "result": "running", "scenario": "compiler_pipe_dogfood"}
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
