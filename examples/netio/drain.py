"""Drain inherited worker-output pipes in readiness order with explicit bounds.

Usage: drain.py SECONDS MAX_BYTES_PER_PIPE FD [FD ...]
The launcher owns child processes. This program owns the passed descriptors and
closes all of them on success, deadline expiry, output overflow or read failure.
"""

import math
import sys
import time

from netio import DefaultSelector, EVENT_READ, close_fd, read, set_blocking


def drain(fds: list[int], seconds: float, maximum: int) -> None:
    if not math.isfinite(seconds) or seconds <= 0 or maximum <= 0 or maximum > 16777216:
        raise ValueError("positive deadline and 1..16777216 byte bound required")
    if len(set(fds)) != len(fds):
        raise ValueError("pipe descriptors must be unique")
    pending: dict[int, bytes] = {}
    deadline = time.monotonic() + seconds
    try:
        with DefaultSelector() as selector:
            for index in range(len(fds)):
                fd = fds[index]
                set_blocking(fd, False)
                selector.register(fd, EVENT_READ, index)
                pending[fd] = b""
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("worker output deadline expired")
                for key, events in selector.select(remaining):
                    try:
                        chunk = read(key.fd, min(65536, maximum - len(pending[key.fd]) + 1))
                    except BlockingIOError:
                        continue
                    if chunk:
                        if len(pending[key.fd]) + len(chunk) > maximum:
                            raise ValueError("worker output exceeds configured bound")
                        pending[key.fd] += chunk
                    else:
                        selector.unregister(key.fd)
                        print("done", key.data, pending[key.fd].hex())
                        sys.stdout.flush()
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
