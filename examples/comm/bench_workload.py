"""Deterministic local API workloads; timings belong to the external harness."""

import sys
import time
from comm import Context
from record_worker import transfer_record


def records(count: int, size: int) -> int:
    payload = b"x" * size
    checksum = 0
    with Context(capacity=1, byte_limit=max(1, size * 2)) as ctx:
        for i in range(count):
            result = transfer_record(ctx, payload, i)
            checksum += len(result)
    return checksum


def reductions(count: int, size: int) -> float:
    # Exactly representable values make equality independent of decimal printing.
    values = [float(i % 31) * 0.25 for i in range(size)]
    expected = [value * 2.0 for value in values]
    checksum = 0.0
    with Context(capacity=1, byte_limit=max(1, size * 32)) as ctx:
        source = ctx.from_f64(values)
        other = ctx.from_f64(values)
        destination = ctx.buffer("f64", size)
        peer = ctx.buffer("f64", size)
        for i in range(count):
            request = ctx.allreduce_sum([source, other], [destination, peer], i)
            progressed = ctx.progress(1)
            assert progressed == 1
            event = ctx.peek()
            assert event is not None and event.request_id == request
            assert event.status == 0 and event.tag == i and event.kind == 4
            ctx.ack(request)
            result = destination.to_f64()
            assert result == expected
            if size:
                checksum += result[-1]
    return checksum


def main() -> None:
    mode = sys.argv[1]
    count = int(sys.argv[2])
    size = int(sys.argv[3])
    if count < 1 or size < 0:
        raise ValueError("positive count and nonnegative size required")
    start = time.perf_counter()
    if mode == "records":
        checksum = float(records(count, size))
    elif mode == "reduce":
        checksum = reductions(count, size)
    else:
        raise ValueError("unknown workload")
    elapsed = time.perf_counter() - start
    print(mode, count, size, checksum, elapsed)


if __name__ == "__main__":
    main()
