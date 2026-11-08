"""Independent CPython socket/selectors baseline for source_exchange.py's protocol."""

import errno
import selectors
import socket
import sys
import time


def exchange(port, chunks, rounds, concurrency):
    if rounds < 1 or not 1 <= concurrency <= 64 or not chunks:
        raise ValueError("invalid workload bounds")
    count = rounds * len(chunks)
    submitted = completed = transferred = steps = 0
    pending = {}
    deadline = time.monotonic() + 60
    with selectors.DefaultSelector() as selector:
        try:
            while completed < count:
                while submitted < count and len(pending) < concurrency:
                    payload = chunks[submitted % len(chunks)]
                    connection = socket.socket()
                    pending[connection] = [b"E" + payload, 0, bytearray(), payload]
                    connection.setblocking(False)
                    error = connection.connect_ex(("127.0.0.1", port))
                    if error not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
                        raise OSError(error, "connect failed")
                    selector.register(connection, selectors.EVENT_WRITE)
                    submitted += 1
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("source exchange deadline expired")
                ready = selector.select(min(5, remaining))
                steps += 1
                for key, mask in ready:
                    connection = key.fileobj
                    state = pending[connection]
                    if mask & selectors.EVENT_WRITE:
                        error = connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        if error:
                            raise OSError(error, "connect failed")
                        try:
                            sent = connection.send(state[0][state[1]:])
                        except BlockingIOError:
                            continue
                        if sent == 0:
                            raise OSError("socket stopped accepting source bytes")
                        state[1] += sent
                        if state[1] == len(state[0]):
                            connection.shutdown(socket.SHUT_WR)
                            selector.modify(connection, selectors.EVENT_READ)
                    elif mask & selectors.EVENT_READ:
                        try:
                            part = connection.recv(4096)
                        except BlockingIOError:
                            continue
                        if part:
                            state[2].extend(part)
                            if len(state[2]) > len(state[3]):
                                raise AssertionError("peer exceeded exact source length")
                        else:
                            if bytes(state[2]) != state[3]:
                                raise AssertionError("source bytes changed during exchange")
                            transferred += len(state[2])
                            selector.unregister(connection)
                            del pending[connection]
                            connection.close()
                            completed += 1
        finally:
            for connection in pending:
                connection.close()
    return transferred, completed, steps


def main():
    path, port, chunk_size, concurrency, rounds = sys.argv[1:]
    port, chunk_size, concurrency, rounds = map(int, (port, chunk_size, concurrency, rounds))
    if not 1 <= chunk_size <= 65535:
        raise ValueError("chunk_size must be between 1 and 65535")
    with open(path, "rb") as source:
        data = source.read(1048577)
    if len(data) > 1048576:
        raise ValueError("source input exceeds the 1 MiB dogfood bound")
    chunks = [data[start:start + chunk_size] for start in range(0, len(data), chunk_size)] or [b""]
    exchange(port, chunks, 1, concurrency)
    started = time.perf_counter()
    count, requests, steps = exchange(port, chunks, rounds, concurrency)
    elapsed = time.perf_counter() - started
    print(elapsed, count, requests, steps)


if __name__ == "__main__":
    main()
