"""One unchanged, bounded socket consumer for native and Python runtimes.

Pairs and selector registrations survive every sample. Every received fragment
is compared with its stream's binary payload inside the measured consumer.
"""

from time import perf_counter_ns

from netio import DefaultSelector, EVENT_READ, Socket, socketpair


def transfer(writers: list[Socket], readers: list[Socket], selector: DefaultSelector,
             payloads: list[bytes], iterations: int, sparse: bool) -> int:
    total = 0
    count = len(writers)
    for turn in range(iterations):
        active = [turn % count] if sparse else list(range(count))
        sent = [0] * count
        received = [0] * count
        pending = len(active)
        while pending:
            for index in active:
                payload = payloads[index]
                if sent[index] < len(payload):
                    try:
                        written = writers[index].send(payload[sent[index]:])
                    except BlockingIOError:
                        continue
                    if written <= 0:
                        raise RuntimeError("socket send made no progress")
                    sent[index] += written
            events = selector.select(1.0)
            if not events:
                raise TimeoutError("socket consumer made no progress within one second")
            for key, mask in events:
                index = key.data
                if index is None or index not in active or not mask & EVENT_READ:
                    raise AssertionError("unexpected readiness event")
                payload = payloads[index]
                try:
                    chunk = readers[index].recv(len(payload) - received[index])
                except BlockingIOError:
                    continue
                if not chunk:
                    raise AssertionError("premature EOF")
                end = received[index] + len(chunk)
                if chunk != payload[received[index]:end]:
                    raise AssertionError("binary payload differs")
                received[index] = end
                total += len(chunk)
                if end == len(payload):
                    pending -= 1
    return total


def run(case: str, iterations: int, warmups: int, samples: int) -> None:
    if iterations <= 0 or warmups < 0 or samples <= 0:
        raise ValueError("positive iterations/samples and nonnegative warmups required")
    count = 1
    size = 64
    sparse = False
    if case == "fanin_4k":
        count = 16
        size = 4096
    elif case == "sparse_64":
        count = 64
        sparse = True
    elif case == "bulk_64k":
        count = 4
        size = 65536
    elif case != "pair_64":
        raise ValueError("unknown socket workload")
    payloads = [(bytes([index]) + b"\x00\xffPystachy-io" * (size // 12 + 1))[:size]
                for index in range(count)]
    writers: list[Socket] = []
    readers: list[Socket] = []
    selector = DefaultSelector()
    try:
        for index in range(count):
            left, right = socketpair()
            writers.append(left)
            readers.append(right)
            left.setblocking(False)
            right.setblocking(False)
            selector.register(right, EVENT_READ, index)
        start = perf_counter_ns()
        checksum = transfer(writers, readers, selector, payloads, iterations, sparse)
        elapsed = perf_counter_ns() - start
        print("first", checksum, elapsed)
        for _ in range(warmups):
            checksum = transfer(writers, readers, selector, payloads, iterations, sparse)
            print("warmup", checksum)
        for _ in range(samples):
            start = perf_counter_ns()
            checksum = transfer(writers, readers, selector, payloads, iterations, sparse)
            elapsed = perf_counter_ns() - start
            print("sample", checksum, elapsed)
    finally:
        selector.close()
        for connection in writers:
            connection.close()
        for connection in readers:
            connection.close()
