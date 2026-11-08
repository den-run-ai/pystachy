"""Bounded POSIX process jobs for a dedicated CPython coordinator.

Run this scope in a dedicated coordinator's main thread. It owns a process group;
children must not daemonize or detach. Memory is an admission estimate, not a
kernel-enforced RSS limit. Numeric libraries must honor the declared CPU budget.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


MAX_JOBS = 2
MAX_TIMEOUT = 900


class Resources:
    """Reservations for one complete child process tree."""

    def __init__(self, cpu=1, memory_bytes=0, input_bytes=0):
        for name, value in (("cpu", cpu), ("memory_bytes", memory_bytes), ("input_bytes", input_bytes)):
            if type(value) is not int or value < (1 if name == "cpu" else 0):
                raise ValueError(f"invalid {name} reservation")
        self.cpu, self.memory_bytes, self.input_bytes = cpu, memory_bytes, input_bytes

    def as_dict(self):
        return {name: getattr(self, name) for name in ("cpu", "memory_bytes", "input_bytes")}


class Budget:
    """Shared admission limits; only one unstarted descriptor is prefetched.

    input_bytes limits active input artifacts. queued_bytes limits the single
    pending job's declared inputs. Input contents are never loaded by scheduling.
    """

    def __init__(self, cpu, memory_bytes, input_bytes, queued_bytes=None):
        self.limit = Resources(cpu, memory_bytes, input_bytes)
        if cpu > MAX_JOBS:
            raise ValueError(f"CPU budget must be at most {MAX_JOBS}")
        self.queued_bytes = input_bytes if queued_bytes is None else queued_bytes
        if type(self.queued_bytes) is not int or self.queued_bytes < 0:
            raise ValueError("invalid queued input budget")

    def validate(self, request):
        if any(getattr(request, name) > value for name, value in self.limit.as_dict().items()):
            raise ValueError("job reservation exceeds total resource budget")
        if request.input_bytes > self.queued_bytes:
            raise ValueError("job input exceeds queued byte budget")

    def fits(self, request, used):
        return all(used[name] + getattr(request, name) <= value
                   for name, value in self.limit.as_dict().items())


class Job:
    """An explicit argv command; no shell, pickle, or shared mutable heap."""

    def __init__(self, key, argv, resources=None, *, cwd=None, env=None, stdin=None):
        if not isinstance(argv, (tuple, list)) or not argv or any(
                not isinstance(x, str) or "\0" in x for x in argv):
            raise ValueError("command must be a nonempty string argv")
        self.key, self.argv = key, list(argv)
        self.resources = resources if resources is not None else Resources()
        self.cwd, self.env, self.stdin = cwd, env, stdin


def group_members():
    """Living members of our own group, in the caller's PID namespace.

    Hosted Linux sessions can expose an outer /proc mount. Never pass its outer
    PID directly to kill(): NSpid maps it to the namespace used by os.kill().
    Workers must stay in this group; deliberate daemonization is unsupported.
    """
    if Path("/proc/self/stat").is_file():
        own = Path("/proc/self/stat").read_text()
        group = int(own[own.rfind(")") + 2:].split()[2])
        status = Path("/proc/self/status").read_text().splitlines()
        ids = next(line.split()[1:] for line in status if line.startswith("NSpid:"))
        depth = len(ids)
        members = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat = (entry / "stat").read_text()
                fields = stat[stat.rfind(")") + 2:].split()
                if fields[0] == "Z" or int(fields[2]) != group:
                    continue
                status = (entry / "status").read_text().splitlines()
                ids = next(line.split()[1:] for line in status if line.startswith("NSpid:"))
                if len(ids) == depth and int(ids[-1]) != os.getpid():
                    members.append(int(ids[-1]))
            except (OSError, ValueError, IndexError, StopIteration):
                continue
        return members
    with subprocess.Popen(["ps", "-A", "-o", "pid=,pgid="], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as listing:
        output, error = listing.communicate()
        if listing.returncode:
            raise RuntimeError(f"cannot enumerate owned process group: {error}")
        rows = output.splitlines()
    return [int(pid) for row in rows for pid, group in [row.split()]
            if int(group) == os.getpgrp() and int(pid) not in (os.getpid(), listing.pid)]


class Commands:
    """Bounded subprocess ownership without detached per-worker sessions.

    The coordinator owns one process group. Children inherit it, so an outer
    controller can still cancel the entire group. Exiting the scope terminates
    and reaps children before returning. Callers must reject failed results
    before resuming run(), which yields completions before starting queued work.
    """

    def __init__(self, owns_group=True, cleanup_grace=0.25,
                 output_limit_bytes=1024 * 1024, capture_bytes=1024 * 1024):
        if not math.isfinite(cleanup_grace) or not 0 <= cleanup_grace <= 5:
            raise ValueError("cleanup grace must be finite and from 0 to 5 seconds")
        if type(output_limit_bytes) is not int or output_limit_bytes < 1:
            raise ValueError("output limit must be a positive byte count")
        if type(capture_bytes) is not int or capture_bytes < 0:
            raise ValueError("capture size must be nonnegative")
        self.output_limit_bytes, self.capture_bytes = output_limit_bytes, capture_bytes
        self.peak_reserved = {"cpu": 0, "memory_bytes": 0, "input_bytes": 0}
        self.owns_group = owns_group
        self.cleanup_grace = cleanup_grace
        self.running = {}
        self.results = []
        self.interrupted = 0
        self.handlers = {}

    def __enter__(self):
        if self.owns_group and os.getpgrp() != os.getpid():
            os.setpgid(0, 0)
        # Prove enumeration is available before starting work.
        if self.owns_group:
            group_members()
        self.handlers = {sig: signal.signal(sig, self.stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        return self

    def stop(self, signum, frame):
        # A signal during Popen must wait until the returned child is owned.
        self.interrupted = signum

    def check_signal(self):
        if self.interrupted:
            raise InterruptedError(f"worker coordinator interrupted by signal {self.interrupted}")

    def start(self, key, command, env, cwd, resources=None, stdin=None, queued_at=None):
        out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
        start = time.monotonic()
        input_stream = None
        try:
            if stdin is not None:
                input_stream = open(stdin, "rb")
            proc = subprocess.Popen(command, cwd=cwd, env=env,
                                    stdin=input_stream if input_stream is not None else subprocess.DEVNULL,
                                    stdout=out, stderr=err)
        except BaseException:
            out.close()
            err.close()
            raise
        finally:
            if input_stream is not None:
                input_stream.close()
        self.running[proc.pid] = {"process": proc, "key": key, "command": command, "out": out, "err": err,
                                  "start": start,
                                  "timed_out": False, "cancelled": False,
                                  "resources": resources or Resources(), "queued_at": queued_at or start}
        for name in self.peak_reserved:
            used = sum(getattr(s["resources"], name) for s in self.running.values())
            self.peak_reserved[name] = max(self.peak_reserved[name], used)
        self.check_signal()

    def finish(self, pid, status, usage):
        state = self.running.pop(pid)
        proc = state["process"]
        proc.returncode = os.waitstatus_to_exitcode(status)
        # A completed child can leave a huge sparse file in a single syscall.
        # Check sizes before hashing: output limits also bound cleanup work.
        # Snapshot each size so a surviving descendant cannot keep this reader
        # busy indefinitely by appending while its parent is being reaped.
        sizes = {name: os.fstat(state[name].fileno()).st_size for name in ("out", "err")}
        oversized = sum(sizes.values()) > self.output_limit_bytes
        remaining = self.output_limit_bytes if oversized else sum(sizes.values())
        data, hashes, hashed, prefixes = {}, {}, {}, {}
        for name in ("out", "err"):
            stream = state[name]
            stream.seek(0)
            digest, captured, size = hashlib.sha256(), bytearray(), 0
            limit = min(sizes[name], remaining)
            while size < limit:
                chunk = stream.read(min(65536, limit - size))
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
                captured.extend(chunk[:max(0, self.capture_bytes - len(captured))])
            remaining -= size
            complete = size == sizes[name]
            data[name], hashed[name] = bytes(captured), size
            hashes[name] = digest.hexdigest() if complete else None
            prefixes[name] = None if complete else digest.hexdigest()
            stream.close()
        result = {"key": state["key"], "command": state["command"], "exit_code": proc.returncode,
                "timed_out": state["timed_out"], "cancelled": state["cancelled"],
                "wall_s": time.monotonic() - state["start"],
                "queue_s": state["start"] - state["queued_at"],
                "started_monotonic_s": state["start"], "finished_monotonic_s": time.monotonic(),
                "resources": state["resources"].as_dict(),
                "output_limit_exceeded": oversized,
                "stdout_bytes": sizes["out"], "stderr_bytes": sizes["err"],
                "stdout_truncated": sizes["out"] > len(data["out"]),
                "stderr_truncated": sizes["err"] > len(data["err"]),
                "cpu_s": usage.ru_utime + usage.ru_stime,
                "stdout_sha256": hashes["out"],
                "stderr_sha256": hashes["err"],
                "stdout_hashed_bytes": hashed["out"], "stderr_hashed_bytes": hashed["err"],
                "stdout_prefix_sha256": prefixes["out"], "stderr_prefix_sha256": prefixes["err"],
                "stdout": data["out"].decode("utf-8", "backslashreplace"),
                "stderr": data["err"].decode("utf-8", "backslashreplace")}
        self.results.append(result)
        return result

    def run(self, commands, env, timeout=60, jobs=1, cwd=None, *, budget=None):
        if (type(jobs) is not int or not 1 <= jobs <= MAX_JOBS
                or not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT):
            raise ValueError(f"require 1..{MAX_JOBS} jobs and a finite timeout in (0, {MAX_TIMEOUT}] seconds")
        if budget is None:
            budget = Budget(jobs, 0, 0)
        pending = iter(commands)
        exhausted, waiting, queued_at = False, None, 0.0
        while self.running or waiting is not None or not exhausted:
            self.check_signal()
            # Yield every observed completion before any queued launch. Callers
            # reject failed results here, so no later job starts after failure.
            ready = []
            for pid, state in list(self.running.items()):
                now = time.monotonic()
                waited, status, usage = os.wait4(pid, os.WNOHANG)
                if waited:
                    ready.append(self.finish(pid, status, usage))
                elif sum(
                        os.fstat(state[name].fileno()).st_size for name in ("out", "err")) > self.output_limit_bytes:
                    raise RuntimeError(f"command {state['key']} exceeded output byte limit")
                elif now - state["start"] >= timeout:
                    state["timed_out"] = True
                    raise TimeoutError(f"command {state['key']} exceeded {timeout:g} seconds")
            for result in ready:
                if result["output_limit_exceeded"]:
                    raise RuntimeError(f"command {result['key']} exceeded output byte limit")
                yield result
            self.check_signal()
            while not exhausted and len(self.running) < jobs:
                if waiting is None:
                    try:
                        item = next(pending)
                    except StopIteration:
                        exhausted = True
                        break
                    waiting = item if isinstance(item, Job) else Job(*item)
                    queued_at = time.monotonic()
                    budget.validate(waiting.resources)
                used = {name: sum(getattr(state["resources"], name) for state in self.running.values())
                        for name in self.peak_reserved}
                if not budget.fits(waiting.resources, used):
                    break  # FIFO keeps placement and starvation behavior simple.
                self.start(waiting.key, waiting.argv,
                           env if waiting.env is None else waiting.env,
                           cwd if waiting.cwd is None else waiting.cwd,
                           waiting.resources, waiting.stdin, queued_at)
                waiting = None
            if self.running:
                time.sleep(0.005)

    def __exit__(self, exc_type, exc, tb):
        # All descendants share this exclusively owned group. TERM reaches
        # grandchildren even if their worker already exited. Keep the parent
        # alive to save a failure report and escalate only remaining members.
        for sig in self.handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            for state in self.running.values():
                state["cancelled"] = True
            members = group_members() if self.owns_group else list(self.running)
            if members and self.owns_group:
                os.killpg(os.getpgrp(), signal.SIGTERM)
            elif members:
                for state in self.running.values():
                    try:
                        state["process"].terminate()
                    except ProcessLookupError:
                        pass
            if members:
                deadline = time.monotonic() + self.cleanup_grace
                while members and time.monotonic() < deadline:
                    time.sleep(0.01)
                    if self.owns_group:
                        members = group_members()
                    else:
                        for pid in list(self.running):
                            waited, status, usage = os.wait4(pid, os.WNOHANG)
                            if waited:
                                self.finish(pid, status, usage)
                        members = list(self.running)
                for pid in members:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            for pid in list(self.running):
                _, status, usage = os.wait4(pid, 0)
                self.finish(pid, status, usage)
        finally:
            for sig, handler in self.handlers.items():
                signal.signal(sig, handler)
        if self.interrupted and exc is None:
            raise InterruptedError(f"worker coordinator interrupted by signal {self.interrupted}")
