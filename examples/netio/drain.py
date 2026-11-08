"""Drain inherited worker-output pipes in readiness order with explicit bounds.

Usage: drain.py SECONDS MAX_BYTES_PER_PIPE FD [FD ...]
The launcher owns child processes. This program owns the passed descriptors and
closes all of them on success, deadline expiry, output overflow or read failure.
"""

import math
import sys
import time

from netio import DefaultSelector, EVENT_READ, close_fd, read, set_blocking


class Output:
    """Bound fragment overhead; one final value() copies each byte at most twice."""

    def __init__(self) -> None:
        self.size = 0
        self.chunks: list[bytes] = []
        self.blocks: list[bytes] = []

    def append(self, chunk: bytes) -> None:
        self.size += len(chunk)
        self.chunks.append(chunk)
        # Even one-byte reads retain at most one object per 256 bytes, plus
        # an unfinished batch. No join below recopies an earlier block.
        if len(self.chunks) == 256:
            self.blocks.append(b"".join(self.chunks))
            self.chunks = []

    def value(self) -> bytes:
        return b"".join(self.blocks + self.chunks)


def remaining(deadline: float) -> float:
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("worker output deadline expired")
    return seconds


def drain(fds: list[int], seconds: float, maximum: int) -> None:
    if not math.isfinite(seconds) or seconds <= 0 or maximum <= 0 or maximum > 16777216:
        raise ValueError("positive deadline and 1..16777216 byte bound required")
    if len(set(fds)) != len(fds):
        raise ValueError("pipe descriptors must be unique")
    pending: dict[int, Output] = {}
    deadline = time.monotonic() + seconds
    try:
        with DefaultSelector() as selector:
            for index in range(len(fds)):
                fd = fds[index]
                set_blocking(fd, False)
                selector.register(fd, EVENT_READ, index)
                pending[fd] = Output()
            while pending:
                for key, events in selector.select(remaining(deadline)):
                    # A ready result can arrive after the wait's deadline, or
                    # an earlier event can consume the remaining batch time.
                    remaining(deadline)
                    try:
                        chunk = read(key.fd, min(65536, maximum - pending[key.fd].size + 1))
                    except BlockingIOError:
                        continue
                    if chunk:
                        size = pending[key.fd].size + len(chunk)
                        if size > maximum:
                            raise ValueError("worker output exceeds configured bound")
                        pending[key.fd].append(chunk)
                    else:
                        selector.unregister(key.fd)
                        encoded = pending[key.fd].value().hex()
                        remaining(deadline)
                        print("done", key.data, encoded)
                        sys.stdout.flush()
                        encoded = ""
                        del pending[key.fd]
    finally:
        for fd in fds:
            try:
                close_fd(fd)
            except OSError:
                pass


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise ValueError("usage: drain.py SECONDS MAX_BYTES_PER_PIPE FD [FD ...]")
    drain([int(value) for value in sys.argv[3:]], float(sys.argv[1]), int(sys.argv[2]))
