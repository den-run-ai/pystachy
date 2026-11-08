"""Linux job supervisor; the private protocol never uses command output streams.

Each supervisor remains in the coordinator's process group and adopts orphaned
descendants. Only the kernel's ECHILD result completes its whole-tree ownership.
The coordinator must itself be a subreaper in case this supervisor fails.
"""
from __future__ import annotations

import ctypes
import errno
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def _prctl(option, argument):
    if sys.platform != "linux":
        raise OSError(errno.ENOTSUP, "process workers require Linux child subreapers")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(option, argument, 0, 0, 0) == -1:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def get_subreaper():
    value = ctypes.c_int()
    _prctl(37, ctypes.addressof(value))  # PR_GET_CHILD_SUBREAPER
    return value.value


def set_subreaper(value):
    if value not in (0, 1):
        raise ValueError("child subreaper setting must be zero or one")
    _prctl(36, int(value))  # PR_SET_CHILD_SUBREAPER


def _status(path):
    return {name: value.split() for line in path.read_text().splitlines()
            for name, separator, value in [line.partition(":")] if separator}


def direct_children():
    """Snapshot direct children in the caller's namespace, without reaping any.

    /proc can belong to an outer PID namespace. Both its child list and PPid
    fields use that mount's IDs; NSpid translates them to the caller's depth.
    Some kernels omit the children file, so PPid enumeration is the fallback.
    A single-threaded owner with default SIGCHLD must not reap between taking
    this snapshot and signaling it: unreaped children keep their PIDs reserved.
    An empty snapshot is not proof that the kernel child set is empty.
    """
    own = _status(Path("/proc/thread-self/status"))
    depth = len(own["NSpid"])
    outer_pid = own["Pid"][0]
    if own["Tgid"][0] != outer_pid or int(own["NSpid"][-1]) != os.getpid():
        raise RuntimeError("process workers require a coordinator's main thread")
    try:
        entries = [Path("/proc") / pid for pid in Path("/proc/thread-self/children").read_text().split()]
    except FileNotFoundError:
        entries = [path for path in Path("/proc").iterdir() if path.name.isdigit()]
    children = []
    for entry in entries:
        try:
            status = _status(entry / "status")
        except (FileNotFoundError, ProcessLookupError):
            continue  # Unrelated processes may disappear during enumeration.
        if status["PPid"][0] == outer_pid:
            ids = status["NSpid"]
            if len(ids) < depth:
                raise RuntimeError("cannot map owned child into the coordinator's PID namespace")
            children.append(int(ids[depth - 1]))
    return children


def signal_children(signum, notified=None):
    """Signal a direct-child snapshot before any of its PIDs can be reaped.

    An optional notified set deduplicates TERM during the grace period. The
    caller must remove reaped PIDs from it before those numbers can be reused.
    """
    for pid in direct_children():
        if notified is not None and pid in notified:
            continue
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass
        if notified is not None:
            notified.add(pid)


def _send(control, message):
    data = json.dumps(message, ensure_ascii=True, separators=(",", ":")).encode() + b"\n"
    if len(data) >= 4096:
        raise RuntimeError("worker supervisor control message is too large")
    while data:
        written = os.write(control, data)
        if written == 0:
            raise BrokenPipeError("worker supervisor control pipe closed")
        data = data[written:]


def _reap(process, leader_status, notified):
    # Bound one batch so a continually forking command cannot starve a pending
    # cancellation. No process is reaped between a snapshot and its signals.
    for _ in range(64):
        try:
            pid, status, _ = os.wait4(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        if not pid:
            return False
        notified.discard(pid)
        if pid == process.pid:
            leader_status.append(status)
            process.returncode = os.waitstatus_to_exitcode(status)
    return False


def _wait_tree(process, leader_status, stopped, grace, *, cancel=False):
    deadline = None
    notified = set()
    while True:
        failed = bool(leader_status and os.waitstatus_to_exitcode(leader_status[0]))
        if deadline is None and (cancel or stopped[0] or failed):
            deadline = time.monotonic() + grace
        if deadline is not None:
            if time.monotonic() < deadline:
                signal_children(signal.SIGTERM, notified)
            else:
                # Killing a parent can adopt children absent from this snapshot.
                # Keep killing and reaping until the kernel confirms ECHILD.
                signal_children(signal.SIGKILL)
        if _reap(process, leader_status, notified):
            return
        time.sleep(0.005)


def supervise(control, grace, command):
    process = None
    leader_status = []
    stopped = [0]

    def stop(signum, frame):
        # Signals never interrupt Popen before its returned child is registered.
        stopped[0] = signum

    try:
        os.set_inheritable(control, False)
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        set_subreaper(True)
        direct_children()  # Verify namespace-safe enumeration before launch.
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})
        # The command inherits exactly its stdin/stdout/stderr, cwd and env.
        # close_fds keeps the supervisor's private control pipe out of workers.
        process = subprocess.Popen(command, close_fds=True)
        _send(control, {"event": "started", "pid": process.pid})
        _wait_tree(process, leader_status, stopped, grace)
        if not leader_status:
            raise RuntimeError("worker leader exited without a wait status")
        _send(control, {"event": "finished", "status": leader_status[0]})
        return 0
    except BaseException as error:
        if process is not None:
            try:
                _wait_tree(process, leader_status, stopped, grace, cancel=True)
            except BaseException:
                # The coordinator is also a subreaper and must take ownership
                # when this helper exits without a finished message.
                pass
        try:
            _send(control, {"event": "error", "type": type(error).__name__,
                            "errno": getattr(error, "errno", None), "message": str(error)[:240]})
        except (OSError, RuntimeError):
            pass
        return 1
    finally:
        os.close(control)


def main():
    control = int(sys.argv[1])
    grace = float(sys.argv[2])
    if not math.isfinite(grace) or not 0 <= grace <= 5 or len(sys.argv) < 4:
        _send(control, {"event": "error", "type": "ValueError", "errno": None,
                        "message": "invalid worker supervisor arguments"})
        os.close(control)
        return 1
    return supervise(control, grace, sys.argv[3:])


if __name__ == "__main__":
    sys.exit(main())
