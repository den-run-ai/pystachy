"""Bounded Linux process jobs shared by compiler and application coordinators.

Run this scope in a dedicated coordinator's main thread. It owns a process group;
children must not daemonize or detach. Memory is an admission estimate, not a
kernel-enforced RSS limit. Numeric libraries must honor the declared CPU budget.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


CHILD_SCRIPT = Path(__file__).resolve().with_name("process_worker_child.py")
_spec = importlib.util.spec_from_file_location("process_worker_child", CHILD_SCRIPT)
child_owner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(child_owner)


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

    The coordinator owns one process group. LLVM commands inherit it, so an
    outer controller can still kill the entire build. Each job has a subreaper
    that stays alive until its entire tree is reaped. Reservations, deadlines
    and output collection cover that lifetime, including an exited leader's
    descendants. The dedicated coordinator must have no other child processes.
    """

    def __init__(self, measure=None, owns_group=True, cleanup_grace=0.25,
                 output_limit_bytes=None, capture_bytes=1024 * 1024):
        if not math.isfinite(cleanup_grace) or not 0 <= cleanup_grace <= 5:
            raise ValueError("cleanup grace must be finite and from 0 to 5 seconds")
        if output_limit_bytes is not None and (type(output_limit_bytes) is not int or output_limit_bytes < 1):
            raise ValueError("output limit must be a positive byte count")
        if type(capture_bytes) is not int or capture_bytes < 0:
            raise ValueError("capture size must be nonnegative")
        self.output_limit_bytes, self.capture_bytes = output_limit_bytes, capture_bytes
        self.peak_reserved = {"cpu": 0, "memory_bytes": 0, "input_bytes": 0}
        self.measure = measure
        self.owns_group = owns_group
        self.cleanup_grace = cleanup_grace
        self.running = {}
        self.results = []
        self.interrupted = 0
        self.handlers = {}
        self.previous_subreaper = None

    def __enter__(self):
        if sys.platform != "linux":
            raise RuntimeError("process workers require Linux child subreapers")
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            raise RuntimeError("process workers require the default SIGCHLD handler")
        # Cleanup may adopt children of a failed supervisor. An exclusively
        # owned child set is necessary before enabling this process-wide role.
        try:
            os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            pass
        else:
            raise RuntimeError("process workers require a coordinator without existing children")
        if self.owns_group and os.getpgrp() != os.getpid():
            os.setpgid(0, 0)
        self.previous_subreaper = child_owner.get_subreaper()
        try:
            child_owner.direct_children()  # Fail before spawning if /proc is unavailable.
            child_owner.set_subreaper(True)
            for sig in (signal.SIGINT, signal.SIGTERM):
                self.handlers[sig] = signal.signal(sig, self.stop)
        except BaseException:
            child_owner.set_subreaper(self.previous_subreaper)
            for sig, handler in self.handlers.items():
                signal.signal(sig, handler)
            raise
        return self

    def stop(self, signum, frame):
        # A signal during Popen must wait until the returned child is owned.
        self.interrupted = signum

    def check_signal(self):
        if self.interrupted:
            raise InterruptedError(f"backend interrupted by signal {self.interrupted}")

    def read_control(self, state):
        """Read a bounded private channel; workers never inherit its descriptor."""
        while not state["control_eof"]:
            try:
                data = os.read(state["control"], 4096)
            except BlockingIOError:
                break
            if not data:
                state["control_eof"] = True
                break
            state["control_data"] += data
            if len(state["control_data"]) > 8192:
                raise RuntimeError("worker supervisor exceeded control message limit")
        while b"\n" in state["control_data"]:
            line, state["control_data"] = state["control_data"].split(b"\n", 1)
            message = json.loads(line)
            event = message.get("event") if isinstance(message, dict) else None
            if event == "started" and not state["started"]:
                state["started"] = True
            elif event == "finished" and "worker_status" not in state and type(message.get("status")) is int:
                state["worker_status"] = message["status"]
            elif event == "error" and "launch_error" not in state:
                state["launch_error"] = message
            else:
                raise RuntimeError("invalid worker supervisor control message")

    def start(self, key, command, env, cwd, resources=None, stdin=None, queued_at=None, timeout=60, on_tick=None):
        out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
        control, writer = os.pipe()
        os.set_blocking(control, False)
        start = time.monotonic()
        input_stream = None
        # The helper inherits this mask, installs its handlers, then unmasks.
        # Register it before restoring our mask, including a signal in Popen.
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            if stdin is not None:
                input_stream = open(stdin, "rb")
            proc = subprocess.Popen([sys.executable, "-I", str(CHILD_SCRIPT), str(writer),
                                     str(self.cleanup_grace), *command], cwd=cwd, env=env,
                                    stdin=input_stream if input_stream is not None else subprocess.DEVNULL,
                                    stdout=out, stderr=err, pass_fds=(writer,))
            state = {"process": proc, "key": key, "command": command, "out": out, "err": err,
                     "start": start, "peak": 0, "processes": 0, "sampled": 0,
                     "proc_pid": None, "load": list(os.getloadavg()),
                     "timed_out": False, "cancelled": False,
                     "resources": resources or Resources(), "queued_at": queued_at or start,
                     "control": control, "control_data": b"", "control_eof": False, "started": False}
            self.running[proc.pid] = state
        except BaseException:
            out.close()
            err.close()
            os.close(control)
            raise
        finally:
            os.close(writer)
            if input_stream is not None:
                input_stream.close()
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        for name in self.peak_reserved:
            used = sum(getattr(s["resources"], name) for s in self.running.values())
            self.peak_reserved[name] = max(self.peak_reserved[name], used)
        # Preserve synchronous exec failure: do not admit the next job until
        # the real command is owned, even though Popen launched its supervisor.
        while True:
            self.check_signal()
            if on_tick is not None:
                on_tick()
            self.read_control(state)
            if "launch_error" in state:
                error = state["launch_error"]
                raise OSError(error.get("errno") or 5, error.get("message", "worker launch failed"))
            if state["started"]:
                break
            if state["control_eof"]:
                raise RuntimeError("worker supervisor exited before command startup")
            if time.monotonic() - start >= min(timeout, 5):
                state["timed_out"] = True
                raise TimeoutError(f"command {key} exceeded its startup deadline")
            time.sleep(0.005)
        if self.measure:
            self.running[proc.pid]["proc_pid"] = self.measure.proc_child_pid(proc.pid)

    def finish(self, pid, status, usage, *, cleanup=False):
        state = self.running[pid]
        state["reaped"] = (status, usage)
        proc = state["process"]
        proc.returncode = os.waitstatus_to_exitcode(status)
        self.read_control(state)
        supervisor_complete = proc.returncode == 0 and "worker_status" in state
        if not supervisor_complete and not cleanup:
            raise RuntimeError(f"command {state['key']} lost its worker supervisor")
        self.running.pop(pid)
        os.close(state["control"])
        exit_code = os.waitstatus_to_exitcode(state["worker_status"]) if supervisor_complete else proc.returncode or 1
        # A completed child can leave a huge sparse file in a single syscall.
        # Check sizes before hashing: output limits also bound cleanup work.
        # The supervisor has reaped every descendant before reporting complete;
        # fallback cleanup likewise reaches ECHILD before calling finish.
        sizes = {name: os.fstat(state[name].fileno()).st_size for name in ("out", "err")}
        oversized = self.output_limit_bytes is not None and sum(sizes.values()) > self.output_limit_bytes
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
        result = {"key": state["key"], "command": state["command"], "exit_code": exit_code,
                "supervisor_failed": not supervisor_complete,
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
                "sampled_process_tree_peak_rss_kib": state["peak"] or None,
                "wait4_max_process_rss_kib": usage.ru_maxrss,
                "sampled_max_processes": state["processes"], "load_before": state["load"],
                "proc_pid_resolved": state["proc_pid"] is not None, "load_after": list(os.getloadavg()),
                "stdout_sha256": hashes["out"],
                "stderr_sha256": hashes["err"],
                "stdout_hashed_bytes": hashed["out"], "stderr_hashed_bytes": hashed["err"],
                "stdout_prefix_sha256": prefixes["out"], "stderr_prefix_sha256": prefixes["err"],
                "stdout": data["out"].decode("utf-8", "backslashreplace"),
                "stderr": data["err"].decode("utf-8", "backslashreplace")}
        self.results.append(result)
        return result

    def run(self, commands, env, timeout, jobs=1, cwd=None, *, budget=None, on_tick=None):
        if type(jobs) is not int or not 1 <= jobs <= 64 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("require 1..64 jobs and a positive finite timeout")
        pending = iter(commands)
        exhausted, waiting, queued_at = False, None, 0.0
        while self.running or waiting is not None or not exhausted:
            self.check_signal()
            if on_tick is not None:
                on_tick()
            # Yield every observed completion before any queued launch. Callers
            # reject failed results here, so no later job starts after failure.
            ready = []
            for pid, state in list(self.running.items()):
                now = time.monotonic()
                if state["proc_pid"] is not None and now - state["sampled"] >= 0.01:
                    rss, count = self.measure.process_tree_rss(state["proc_pid"])
                    state["peak"] = max(state["peak"], rss)
                    state["processes"] = max(state["processes"], count)
                    state["sampled"] = now
                waited, status, usage = os.wait4(pid, os.WNOHANG)
                if waited:
                    ready.append(self.finish(pid, status, usage))
                elif self.output_limit_bytes is not None and sum(
                        os.fstat(state[name].fileno()).st_size for name in ("out", "err")) > self.output_limit_bytes:
                    raise RuntimeError(f"command {state['key']} exceeded output byte limit")
                elif now - state["start"] >= timeout:
                    state["timed_out"] = True
                    raise TimeoutError(f"backend command {state['key']} exceeded {timeout:g} seconds")
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
                    if budget is not None:
                        budget.validate(waiting.resources)
                used = {name: sum(getattr(state["resources"], name) for state in self.running.values())
                        for name in self.peak_reserved}
                if budget is not None and not budget.fits(waiting.resources, used):
                    break  # FIFO keeps placement and starvation behavior simple.
                self.start(waiting.key, waiting.argv,
                           env if waiting.env is None else waiting.env,
                           cwd if waiting.cwd is None else waiting.cwd,
                           waiting.resources, waiting.stdin, queued_at, timeout, on_tick)
                waiting = None
            if self.running:
                time.sleep(0.005)

    def execute(self, command, env, timeout, cwd=None):
        return next(self.run([(0, command)], env, timeout, cwd=cwd))

    def __exit__(self, exc_type, exc, tb):
        # Supervisors reap their own complete trees. If one dies unexpectedly,
        # this subreaper adopts its children and drains them before returning.
        # ECHILD, never an empty process snapshot, proves cleanup is complete.
        for sig in self.handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            for state in self.running.values():
                state["cancelled"] = True
            if self.running and self.owns_group:
                os.killpg(os.getpgrp(), signal.SIGTERM)
            deadline = time.monotonic() + self.cleanup_grace + 1
            empty = False
            notified = set()
            while not empty:
                # Allow helpers to finish their own TERM/KILL sequence first.
                # A failed/hung helper is then killed and its children adopted.
                signum = signal.SIGKILL if time.monotonic() >= deadline else signal.SIGTERM
                for pid in child_owner.direct_children():
                    if signum == signal.SIGTERM and pid in notified:
                        continue
                    try:
                        os.kill(pid, signum)
                    except ProcessLookupError:
                        pass
                    notified.add(pid)
                while True:
                    try:
                        pid, status, usage = os.wait4(-1, os.WNOHANG)
                    except ChildProcessError:
                        empty = True
                        break
                    if not pid:
                        break
                    notified.discard(pid)
                    if pid in self.running:
                        self.running[pid]["process"].returncode = os.waitstatus_to_exitcode(status)
                        self.running[pid]["reaped"] = (status, usage)
                if not empty:
                    time.sleep(0.005)
            for pid, state in list(self.running.items()):
                self.read_control(state)
                if "launch_error" in state and not state["started"]:
                    self.running.pop(pid)
                    os.close(state["control"])
                    state["out"].close()
                    state["err"].close()
                else:
                    self.finish(pid, *state["reaped"], cleanup=True)
        finally:
            child_owner.set_subreaper(self.previous_subreaper)
            for sig, handler in self.handlers.items():
                signal.signal(sig, handler)
        if self.interrupted and exc is None:
            raise InterruptedError(f"backend interrupted by signal {self.interrupted}")
