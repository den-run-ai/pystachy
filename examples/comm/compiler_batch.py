"""Bounded CPython compiler coordinator exercising local completion buffers.

The compiler processes use OS pipes and artifact files.  ``comm`` only owns the
small completion records inside the coordinator or a persistent record worker;
it is not the interprocess transport or scheduler.
"""

import argparse
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
RECORD_LIMIT = 4096
MAX_WORKERS = 2
MAX_TIMEOUT = 900


@dataclass
class Job:
    job_id: int
    command: list[str]
    artifact: Path
    mode: str = "ir"
    expected_status: int = 0


@dataclass
class Running:
    job: Job
    process: subprocess.Popen
    started: float
    streams: int
    diagnostics: bytearray = field(default_factory=bytearray)
    stream_hashes: dict = field(default_factory=dict)
    stream_sizes: dict = field(default_factory=dict)
    artifact_file: object = None
    record: bytes | None = None


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def kill_group(process):
    # A leader may have exited while a descendant still owns a diagnostic pipe.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@contextmanager
def cancellation_signals():
    """Defer cancellation until every launched process has an owner.

    Raising inside a Python signal handler can interrupt Popen after the child
    starts but before its PID is returned/registered. Keep these non-raising
    handlers installed through cleanup so repeated signals cannot interrupt it.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("compiler batches must run on the main thread")
    received = None
    previous = {}

    def request_cancel(signum, _frame):
        nonlocal received
        if received is None:
            received = signum

    def check_cancelled():
        if received is not None:
            raise SystemExit(128 + received)

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, request_cancel)
        yield check_cancelled
        # Also catch cancellation received during the final resource cleanup.
        check_cancelled()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def record_for(state):
    job = state.job
    if state.process.returncode != job.expected_status:
        raise RuntimeError(f"job {job.job_id} exited {state.process.returncode}, "
                           f"expected {job.expected_status}: "
                           + state.diagnostics.decode("utf-8", "replace"))
    artifact_hash = None
    if job.expected_status == 0:
        if not job.artifact.is_file() or job.artifact.stat().st_size == 0:
            raise RuntimeError(f"job {job.job_id} produced no artifact")
        artifact_hash = digest(job.artifact)
    record = {
        "job": job.job_id,
        "status": state.process.returncode,
        "mode": job.mode,
        "artifact": str(job.artifact),
        "sha256": artifact_hash,
        "diagnostics": {name: {"bytes": state.stream_sizes[name], "sha256": value.hexdigest()}
                        for name, value in state.stream_hashes.items()},
    }
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
    if len(encoded) > RECORD_LIMIT:
        raise ValueError("completion record exceeds bounded pipe record size")
    return encoded


def validate_worker_limits(workers, timeout):
    if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be an integer between 1 and {MAX_WORKERS}")
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be finite, positive and at most {MAX_TIMEOUT} seconds")


def run_batch(jobs, *, workers=2, transport="direct", handler_command=None,
              timeout=120.0, diagnostic_limit=1048576, cwd=ROOT, env=None):
    """Run jobs with bounded admission, concurrent diagnostics and ordered acks.

    One or two workers admit jobs, including completed jobs awaiting
    acknowledgment. The timeout must be finite, positive and at most 900 seconds.
    Completion construction, transfer and decoding all count toward that deadline;
    every active job is checked before an acknowledgment releases its slot.
    Each job owns a separate process group. At most one completion
    record is in flight to the handler. All owned groups are killed and direct
    children reaped on failures, SIGINT or SIGTERM. This POSIX coordinator must
    run on the main thread; cancellation raises SystemExit(128 + signal number)
    after cleanup and restores the caller's signal handlers.
    ``diagnostic_limit`` bounds combined stdout/stderr per job (IR is an artifact)
    and separately bounds handler stderr across acknowledgments and shutdown.
    Handler stdout records and trailing output are bounded by ``RECORD_LIMIT``.
    """
    with cancellation_signals() as check_cancelled:
        return _run_batch(jobs, workers=workers, transport=transport,
                          handler_command=handler_command, timeout=timeout,
                          diagnostic_limit=diagnostic_limit, cwd=cwd, env=env,
                          check_cancelled=check_cancelled)


def _run_batch(jobs, *, workers, transport, handler_command, timeout,
               diagnostic_limit, cwd, env, check_cancelled):
    validate_worker_limits(workers, timeout)
    if diagnostic_limit < 1:
        raise ValueError("invalid diagnostic bound")
    if transport not in ("direct", "comm", "handler"):
        raise ValueError("unknown completion transport")
    if transport == "handler" and not handler_command:
        raise ValueError("handler transport requires a command")
    if len({job.job_id for job in jobs}) != len(jobs):
        raise ValueError("job IDs must be unique")
    if len({job.artifact.resolve() for job in jobs}) != len(jobs):
        raise ValueError("artifact paths must be unique")
    environment = os.environ.copy() if env is None else dict(env)
    waiting = deque(jobs)
    active = {}
    all_processes = []
    pending = deque()
    records = []
    diagnostics_order = []
    context = None
    transfer_record = None
    handler = None
    handler_buffer = bytearray()
    handler_errors = bytearray()
    inflight = None
    peak_admitted = 0
    first_diagnostic = None
    started = time.perf_counter()
    selector = selectors.DefaultSelector()

    def check_active():
        check_cancelled()
        now = time.perf_counter()
        for state in active.values():
            if now - state.started >= timeout:
                raise TimeoutError(f"job {state.job.job_id} exceeded {timeout}s including completion ack")

    def accept(state, received):
        check_active()
        if received != state.record:
            raise AssertionError("completion handler changed or truncated a record")
        record = json.loads(received)
        # Transfer and decoding may take time. Check all jobs immediately before
        # accepting the acknowledgment, while their admission slots remain held.
        check_active()
        records.append(record)
        del active[state.job.job_id]

    def read_handler(key):
        name, _ = key.data
        if name == "handler":
            buffer, limit = handler_buffer, RECORD_LIMIT
            message = "completion handler output exceeds record bound"
        else:
            buffer, limit = handler_errors, diagnostic_limit
            message = "completion handler diagnostics exceed bound"
        remaining = limit - len(buffer)
        # Read at most one byte beyond the remaining budget, and reject it
        # before retaining it. The same buffers and limits apply through EOF.
        chunk = os.read(key.fileobj.fileno(), min(16384, remaining + 1))
        if len(chunk) > remaining:
            raise RuntimeError(message)
        if chunk:
            buffer.extend(chunk)
        else:
            selector.unregister(key.fileobj)
            key.fileobj.close()
        return bool(chunk)

    try:
        check_cancelled()
        if transport == "comm":
            from comm import Context
            from record_worker import transfer_record
            context = Context(capacity=1, byte_limit=2 * RECORD_LIMIT)
        if transport == "handler":
            check_cancelled()
            handler = subprocess.Popen(handler_command, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       cwd=cwd, env=environment, start_new_session=True)
            all_processes.append(handler)
            check_cancelled()
            for name, stream in (("handler", handler.stdout), ("handler_error", handler.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, (name, None))
        while waiting or active or inflight is not None:
            check_active()
            while waiting and len(active) < workers:
                check_active()
                job = waiting.popleft()
                job.artifact.parent.mkdir(parents=True, exist_ok=True)
                if job.artifact.exists():
                    raise FileExistsError(f"refusing stale artifact: {job.artifact}")
                artifact_file = job.artifact.open("xb") if job.mode == "ir" else None
                try:
                    check_active()
                    process = subprocess.Popen(job.command, stdin=subprocess.DEVNULL,
                                               stdout=artifact_file or subprocess.PIPE,
                                               stderr=subprocess.PIPE, cwd=cwd,
                                               env=environment, start_new_session=True)
                except BaseException:
                    if artifact_file:
                        artifact_file.close()
                    raise
                all_processes.append(process)
                streams = [("stderr", process.stderr)]
                if artifact_file is None:
                    streams.append(("stdout", process.stdout))
                state = Running(job, process, time.perf_counter(), len(streams),
                                artifact_file=artifact_file)
                active[job.job_id] = state
                check_active()
                peak_admitted = max(peak_admitted, len(active))
                for name, stream in streams:
                    state.stream_hashes[name] = hashlib.sha256()
                    state.stream_sizes[name] = 0
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, (name, state))

            for state in list(active.values()):
                check_active()
                if state.record is None and state.streams == 0 and state.process.poll() is not None:
                    if state.artifact_file:
                        state.artifact_file.close()
                        state.artifact_file = None
                    record = record_for(state)
                    check_active()
                    state.record = record
                    pending.append(state)

            while pending and inflight is None:
                check_active()
                state = pending.popleft()
                if transport == "handler":
                    # <= PIPE_BUF, with at most one record outstanding: this write
                    # cannot fill a fresh pipe even while the handler starts up.
                    written = os.write(handler.stdin.fileno(), state.record)
                    check_active()
                    if written != len(state.record):
                        raise RuntimeError("short completion record write")
                    inflight = state
                else:
                    received = state.record if context is None else transfer_record(context, state.record, state.job.job_id)
                    accept(state, received)
            # Refill released slots immediately in every transport. Waiting for
            # a selector tick here penalizes inline/direct acknowledgments while
            # handler acknowledgments already return at the end of the loop.
            if not active or (waiting and len(active) < workers):
                continue
            if handler is not None and handler.poll() is not None:
                raise RuntimeError(f"completion handler exited early ({handler.returncode})")
            for key, _ in selector.select(0.02):
                check_active()
                name, state = key.data
                if state is None:
                    if not read_handler(key):
                        if name == "handler" and active:
                            raise RuntimeError("completion handler closed stdout early")
                    elif name == "handler" and b"\n" in handler_buffer:
                        if inflight is None or not handler_buffer.endswith(b"\n") or handler_buffer.count(b"\n") != 1:
                            raise RuntimeError("unsolicited completion handler output")
                        accept(inflight, bytes(handler_buffer))
                        inflight = None
                        handler_buffer.clear()
                    continue
                chunk = os.read(key.fileobj.fileno(), 16384)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    state.streams -= 1
                    continue
                state.diagnostics.extend(chunk)
                if len(state.diagnostics) > diagnostic_limit:
                    raise RuntimeError(f"job {state.job.job_id} diagnostics exceed {diagnostic_limit} bytes")
                state.stream_hashes[name].update(chunk)
                state.stream_sizes[name] += len(chunk)
                diagnostics_order.append(state.job.job_id)
                if first_diagnostic is None:
                    first_diagnostic = time.perf_counter() - started
        if handler is not None:
            check_cancelled()
            handler.stdin.close()
            handler.stdin = None
            if handler.stdout.closed or handler.stderr.closed:
                raise RuntimeError("completion handler closed a stream before shutdown")
            # Keep bounded, nonblocking reads until both pipes reach EOF and the
            # child exits. Closing pipes does not release the shutdown deadline.
            shutdown_timeout = min(timeout, 5.0)
            deadline = time.perf_counter() + shutdown_timeout
            while selector.get_map() or handler.poll() is None:
                check_cancelled()
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(handler.args, shutdown_timeout)
                for key, _ in selector.select(min(0.02, remaining)):
                    check_cancelled()
                    read_handler(key)
            check_cancelled()
            if handler.returncode or handler_errors or handler_buffer:
                raise RuntimeError("completion handler failed or produced unexpected output: "
                                   + handler_errors.decode("utf-8", "replace"))
        check_cancelled()
        return {"seconds": time.perf_counter() - started, "records": records,
                "completion_order": [record["job"] for record in records],
                "diagnostic_order": diagnostics_order, "first_diagnostic_seconds": first_diagnostic,
                "peak_admitted": peak_admitted, "workers": workers, "transport": transport}
    finally:
        for process in all_processes:
            kill_group(process)
        for process in all_processes:
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        for state in active.values():
            if state.artifact_file:
                state.artifact_file.close()
        selector.close()
        if context is not None:
            context.close()


def default_sources(directory):
    directory.mkdir(parents=True, exist_ok=True)
    sources = [
        "def score(n: int) -> int:\n    total = 0\n    for i in range(n):\n        total += (i * i + 3 * i) % 997\n    return total\nprint(score(20000))\n",
        "def count(n: int) -> int:\n    values = [i % 31 for i in range(n)]\n    total = 0\n    for value in values:\n        total += value * value\n    return total\nprint(count(12000))\n",
    ]
    paths = []
    for index, source in enumerate(sources):
        path = directory / f"input_{index}.py"
        if path.exists() and path.read_text() != source:
            raise FileExistsError(f"refusing different source: {path}")
        path.write_text(source)
        paths.append(path)
    return paths


def compiler_jobs(command, sources, directory, mode):
    jobs = []
    for source in sources:
        modes = ("ir", "aot") if mode == "both" else (mode,)
        for kind in modes:
            job_id = len(jobs)
            artifact = directory / f"job_{job_id}{'.ll' if kind == 'ir' else '.bin'}"
            args = ["ir", str(source)] if kind == "ir" else ["build", str(source), "-o", str(artifact)]
            jobs.append(Job(job_id, command + args, artifact, kind))
    return jobs


def compiler_home(command):
    """Match driver.compiler_home for direct native and hosted invocations.

    Arbitrary interpreter options or wrapper commands can change argv[0] or the
    environment. Require an explicit home instead of guessing their library root.
    The benchmark compiler must use this checkout's loader semantics.
    """
    configured = os.environ.get("PYSTACHY_HOME")
    if configured:
        home = Path(configured)
        return home if home.is_absolute() else ROOT / home
    executable = Path(command[0]).name
    if executable.startswith(("python", "pypy")):
        if len(command) == 2 and not command[1].startswith("-"):
            entrypoint = command[1]
        elif command[1:] == ["-m", "pystachy"]:
            if os.environ.get("PYTHONSAFEPATH"):
                raise ValueError("set PYSTACHY_HOME for python -m pystachy with PYTHONSAFEPATH")
            entrypoint = str(ROOT / "pystachy.py")
        else:
            raise ValueError("set PYSTACHY_HOME for this hosted compiler command")
    elif len(command) == 1:
        entrypoint = command[0]
    else:
        raise ValueError("set PYSTACHY_HOME for a wrapped compiler command")
    home = ROOT / Path(entrypoint).parent
    return home if (home / "runtime.c").exists() else home / ".."


def input_manifest(command, handler, sources):
    """Conservatively hash compiler/library inputs, including hosted compilers.

    Executable identities alone do not identify ``python -m pystachy`` or the
    library/runtime files read by a native compiler.  Hash the complete source
    families as well as explicit command files and locally discoverable bridges.
    The checkout's hosted loader discovers workload imports before measurement;
    its negative probes and search path are checked again with the file hashes.
    """
    # Compiler jobs run from ROOT, including when the coordinator was started
    # elsewhere. Relative search paths and PYSTACHY_HOME use that same directory.
    home = compiler_home(command)
    paths = set(sources)
    workloads = {}
    for source in sources:
        result = subprocess.run([sys.executable, "-I", str(ROOT / "examples" / "comm" / "compiler_inputs.py"),
                                 str(source), str(home)], cwd=ROOT, capture_output=True, text=True,
                                timeout=MAX_TIMEOUT)
        if result.returncode:
            raise RuntimeError(f"cannot resolve workload imports for {source}: {result.stderr.strip()}")
        workload = json.loads(result.stdout)
        workloads[str(source)] = workload
        paths.update(Path(path) for path in workload["files"])
    for base in {ROOT, home.resolve()}:
        for family in ("src", "lib", "mpz", "ryu"):
            for path in (base / family).rglob("*"):
                if path.suffix in (".py", ".c", ".h", ".so") and path.is_file():
                    paths.add(path)
        for name in ("runtime.py", "runtime.c", "pyembed.c", "pyext.c", "lljit.c", "pystachy.py",
                     "pystachy_cli.py", "pystachy_toolchain.py"):
            if (base / name).is_file():
                paths.add(base / name)
    for family in (ROOT / "examples" / "comm", ROOT / "tools" / "rt_cpython"):
        paths.update(path for path in family.iterdir() if path.suffix in (".py", ".c", ".h", ".so") and path.is_file())
    for argv in (command, handler or []):
        for index, argument in enumerate(argv):
            path = Path(shutil.which(argument) or argument) if index == 0 else Path(argument)
            if path.is_file():
                paths.add(path.resolve())
    # mypyc workers may be launched with ``python -c 'import record_worker'``.
    # Include extension groups and Python entry points selected through PYTHONPATH.
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if value:
            directory = Path(value).resolve()
            if directory.is_dir():
                paths.update(path for path in directory.iterdir()
                             if path.suffix in (".py", ".so") and path.is_file())
    library_dirs = [ROOT / "build" / "comm"]
    library_dirs += [Path(value) for value in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep) if value]
    for directory in library_dirs:
        bridge = directory / "libpystachy_comm.so"
        if bridge.is_file():
            paths.add(bridge.resolve())
    files = {str(path): digest(path) for path in sorted(paths)}
    for workload in workloads.values():
        for path, before in workload["files"].items():
            if files[path] != before:
                raise RuntimeError(f"workload input changed while capturing inputs: {path}")
    return {"files": files, "workloads": workloads,
            "environment": {name: value for name, value in os.environ.items()
                            if name.startswith("PYSTACHY_") or name in ("PYTHONPATH", "PYTHONSAFEPATH", "LD_LIBRARY_PATH")}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--compiler-command", help="JSON argv overrides --compiler")
    parser.add_argument("--directory", required=True, type=Path, help="fresh output directory")
    parser.add_argument("--workers", type=int, default=2, help="parallel compiler jobs (1 or 2)")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--mode", choices=("ir", "aot", "both"), default="both")
    parser.add_argument("--transport", choices=("comm", "handler"), default="comm")
    parser.add_argument("--handler-command", help="JSON argv for persistent newline record echo worker")
    parser.add_argument("--timeout", type=float, default=120,
                        help="positive seconds per job including acknowledgment, at most 900")
    parser.add_argument("--sources", nargs="*", type=Path)
    args = parser.parse_args(argv)
    if args.samples < 1 or args.samples > 30 or args.warmups < 1 or args.warmups > 3:
        parser.error("samples must be 1–30 and warmups must be 1–3")
    try:
        validate_worker_limits(args.workers, args.timeout)
    except ValueError as error:
        parser.error(str(error))
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = {"result": "fail", "samples": [], "warmups": [], "python": sys.version,
              "platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
              "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
              "environment": {name: value for name, value in os.environ.items()
                              if name.startswith("PYSTACHY_") or name in ("PYTHONPATH", "PYTHONSAFEPATH", "LD_LIBRARY_PATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
              "cache_policy": "inherited private/shared cache; one warmup per variant before measured samples",
              "scope": "CPython process coordinator; local owned completion records; no native process transport"}
    try:
        command = json.loads(args.compiler_command) if args.compiler_command else [str(Path(args.compiler).resolve())]
        handler = json.loads(args.handler_command) if args.handler_command else None
        sources = [path.resolve() for path in args.sources] if args.sources else default_sources(directory / "inputs")
        report["sources"] = {str(path): digest(path) for path in sources}
        report["compiler_command"] = command
        report["handler_command"] = handler
        report["inputs"] = input_manifest(command, handler, sources)
        report["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report["git_status"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines()
        expected = {}
        for source in sources:
            oracle = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=args.timeout, check=True)
            if oracle.stderr:
                raise RuntimeError("CPython workload emitted unexpected diagnostics")
            expected[str(source)] = oracle.stdout
        baseline = None
        variants = [("serial_direct", 1, "direct"), ("parallel_direct", args.workers, "direct"),
                    ("parallel_" + args.transport, args.workers, args.transport)]
        for sample in range(-args.warmups, args.samples):
            # Rotate ordering to reduce systematic warm-cache/order bias.
            order = variants[sample % 3:] + variants[:sample % 3]
            for name, workers, transport in order:
                phase = f"warmup_{sample + args.warmups}" if sample < 0 else f"sample_{sample}"
                jobs = compiler_jobs(command, sources, directory / f"{phase}_{name}", args.mode)
                result = run_batch(jobs, workers=workers, transport=transport, handler_command=handler, timeout=args.timeout)
                result["variant"] = name
                result["sample"] = sample
                comparison = []
                for job in jobs:
                    record = next(record for record in result["records"] if record["job"] == job.job_id)
                    source_index = job.job_id // (2 if args.mode == "both" else 1)
                    if job.mode == "aot":
                        execution = subprocess.run([str(job.artifact)], capture_output=True, timeout=args.timeout, check=True)
                        if execution.stdout != expected[str(sources[source_index])] or execution.stderr:
                            raise AssertionError("AOT workload differs from CPython")
                        comparison.append((job.job_id, "aot", hashlib.sha256(execution.stdout).hexdigest(),
                                           record["status"], record["diagnostics"]))
                    else:
                        comparison.append((job.job_id, "ir", record["sha256"],
                                           record["status"], record["diagnostics"]))
                if baseline is None:
                    baseline = comparison
                if comparison != baseline:
                    raise AssertionError("serial/parallel compiler results differ")
                report["warmups" if sample < 0 else "samples"].append(result)
                print(phase, name, f"{result['seconds']:.6f}s", result["completion_order"], flush=True)
        report["inputs_after"] = input_manifest(command, handler, sources)
        if report["inputs"] != report["inputs_after"]:
            raise RuntimeError("consumed inputs changed during measurement")
        report["medians"] = {name: statistics.median(sample["seconds"] for sample in report["samples"] if sample["variant"] == name)
                             for name, _, _ in variants}
        report["result"] = "pass"
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
