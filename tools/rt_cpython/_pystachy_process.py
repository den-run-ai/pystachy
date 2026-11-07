"""CPython twin of process.py's native primitives (not loaded by Pystachy).

The coordinator owns process groups. Use process.Popen, which supplies the
context manager and validates lifetime with the same handle protocol natively.
"""
import atexit
import math
import os
import select
import signal as signals
import subprocess
import sys
import time

_LIMIT = 64
_BYTES = 64 * 1024 * 1024
_RUNNING = 9223372036854775807
_serial = 0
_owned: dict[int, subprocess.Popen] = {}
_communicated: set[int] = set()


def _get(handle: int) -> subprocess.Popen:
    if handle not in _owned:
        raise ValueError("process handle is closed or invalid")
    return _owned[handle]


def _timeout(timeout: float) -> None:
    if not math.isfinite(timeout) or (timeout < 0 and timeout != -1):
        raise ValueError("timeout must be finite, non-negative or -1")


def spawn(args: list[str]) -> int:
    global _serial
    if sys.platform != "linux":
        raise NotImplementedError("native process workers currently require Linux")
    if not 1 <= len(args) <= 4096:
        raise ValueError("argv must contain 1 to 4096 strings")
    if any("\0" in value for value in args):
        raise ValueError("embedded null byte in argv")
    if sum(len(value.encode()) + 1 for value in args) > 1024 * 1024:
        raise ValueError("argv exceeds 1 MiB")
    if not args[0].startswith("/"):
        raise ValueError("argv[0] must be an absolute executable path")
    if len(_owned) >= _LIMIT:
        raise RuntimeError("too many owned processes; close completed handles")
    child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True,
                             close_fds=True, bufsize=0)
    for stream in (child.stdin, child.stdout, child.stderr):
        os.set_blocking(stream.fileno(), False)
    _serial += 1
    _owned[_serial] = child
    return _serial


def pid(handle: int) -> int:
    return _get(handle).pid


def _poll(child: subprocess.Popen) -> int:
    if child.returncode is None:
        result = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if result is not None:
            try:
                os.killpg(child.pid, signals.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
    return _RUNNING if child.returncode is None else child.returncode


def poll(handle: int) -> int:
    return _poll(_get(handle))


def wait(handle: int, timeout: float) -> int:
    _timeout(timeout)
    child = _get(handle)
    deadline = time.monotonic() + timeout
    while _poll(child) == _RUNNING:
        if timeout >= 0 and time.monotonic() >= deadline:
            raise TimeoutError("process wait timed out")
        time.sleep(0.005)
    return child.returncode


def signal(handle: int, signal_number: int) -> None:
    if signal_number not in (signals.SIGTERM, signals.SIGKILL):
        raise ValueError("only terminate and kill are supported")
    child = _get(handle)
    if _poll(child) == _RUNNING:
        try:
            os.killpg(child.pid, signal_number)
        except ProcessLookupError:
            pass


def _stop(child: subprocess.Popen, deadline: float) -> None:
    if _poll(child) == _RUNNING:
        try:
            os.killpg(child.pid, signals.SIGKILL)
        except ProcessLookupError:
            pass
        while _poll(child) == _RUNNING and time.monotonic() < deadline:
            time.sleep(0.005)
    for stream in (child.stdin, child.stdout, child.stderr):
        stream.close()


def close(handle: int) -> None:
    if not handle:
        return
    child = _get(handle)
    _stop(child, time.monotonic() + 1.0)
    if child.returncode is None:
        raise TimeoutError("process did not exit after kill; ownership retained")
    del _owned[handle]
    _communicated.discard(handle)


def communicate(handle: int, input: bytes, timeout: float, max_output: int) -> tuple[bytes, bytes]:
    _timeout(timeout)
    if not 0 <= max_output <= _BYTES:
        raise ValueError("max_output_bytes must be between 0 and 67108864")
    if len(input) > _BYTES:
        raise ValueError("process input exceeds 64 MiB")
    child = _get(handle)
    if handle in _communicated:
        raise ValueError("communicate may only be called once")
    _communicated.add(handle)
    output = [bytearray(), bytearray()]
    sent = 0
    deadline = time.monotonic() + timeout
    try:
        while True:
            if not child.stdin.closed and sent == len(input):
                child.stdin.close()
            done = _poll(child) != _RUNNING
            reads = [s for s in (child.stdout, child.stderr) if not s.closed]
            if done and not reads:
                break
            if timeout >= 0 and time.monotonic() >= deadline:
                raise TimeoutError("process communicate timed out")
            writes = [] if child.stdin.closed else [child.stdin]
            ready_read, ready_write, _ = select.select(reads, writes, [], 0.005)
            if ready_write:
                try:
                    sent += os.write(child.stdin.fileno(), input[sent:sent + 4096])
                except BrokenPipeError:
                    child.stdin.close()
                except BlockingIOError:
                    pass
            for index, stream in enumerate((child.stdout, child.stderr)):
                if stream not in ready_read:
                    continue
                chunk = os.read(stream.fileno(), 4096)
                if not chunk:
                    stream.close()
                elif len(output[0]) + len(output[1]) + len(chunk) > max_output:
                    raise BufferError("process output limit exceeded")
                else:
                    output[index].extend(chunk)
    except BaseException:
        _stop(child, time.monotonic() + 1.0)
        raise
    for stream in (child.stdin, child.stdout, child.stderr):
        stream.close()
    return bytes(output[0]), bytes(output[1])


def _finish() -> None:
    deadline = time.monotonic() + 1.0
    for child in _owned.values():
        if child.returncode is None:
            try:
                os.killpg(child.pid, signals.SIGKILL)
            except ProcessLookupError:
                pass
    for child in _owned.values():
        _stop(child, deadline)


atexit.register(_finish)
