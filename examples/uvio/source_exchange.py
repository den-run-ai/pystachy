"""Bounded echo of compiler source chunks using the unchanged owned libuv wrapper."""

import sys
import time

from uvio import Loop


def source_chunks(path: str, chunk_size: int) -> list[bytes]:
    if chunk_size < 1 or chunk_size > 65535:
        raise ValueError("chunk_size must be between 1 and 65535")
    with open(path, "rb") as source:
        data = source.read(1048577)
    if len(data) > 1048576:
        raise ValueError("source input exceeds the 1 MiB dogfood bound")
    if not data:
        return [b""]
    return [data[start:start + chunk_size] for start in range(0, len(data), chunk_size)]


def exchange(loop: Loop, port: int, chunks: list[bytes], rounds: int, concurrency: int) -> tuple[int, int, int]:
    """Keep admission bounded; match every completion to its exact original bytes."""
    if rounds < 1 or concurrency < 1 or concurrency > 64 or not chunks:
        raise ValueError("rounds, concurrency and chunks must be nonempty and bounded")
    pending: dict[int, bytes] = {}
    submitted = 0
    completed = 0
    transferred = 0
    steps = 0
    requests = rounds * len(chunks)
    while completed < requests:
        while submitted < requests and len(pending) < concurrency:
            payload = chunks[submitted % len(chunks)]
            request = loop.submit("127.0.0.1", port, b"E" + payload, 5000)
            if request in pending:
                raise AssertionError("request ID reused before completion")
            pending[request] = payload
            submitted += 1
        events = loop.run_once()
        steps += 1
        for event in events:
            if event.status != 0:
                raise AssertionError(event.error_name())
            if event.request_id not in pending:
                raise AssertionError("unknown or duplicate completion")
            expected = pending.pop(event.request_id)
            if event.data != expected:
                raise AssertionError("source bytes changed during exchange")
            transferred += len(event.data)
            completed += 1
    if pending or submitted != requests:
        raise AssertionError("incomplete source transfer")
    return transferred, completed, steps


def main() -> None:
    path = sys.argv[1]
    port = int(sys.argv[2])
    chunk_size = int(sys.argv[3])
    concurrency = int(sys.argv[4])
    rounds = int(sys.argv[5])
    chunks = source_chunks(path, chunk_size)
    if concurrency < 1 or concurrency > 64 or rounds < 1:
        raise ValueError("invalid concurrency or rounds")
    # Warm the exact path, including the FFI twin, outside the recorded sample.
    with Loop(capacity=concurrency, byte_limit=chunk_size + 1) as loop:
        exchange(loop, port, chunks, 1, concurrency)
    started = time.perf_counter()
    with Loop(capacity=concurrency, byte_limit=chunk_size + 1) as loop:
        count, requests, steps = exchange(loop, port, chunks, rounds, concurrency)
    elapsed = time.perf_counter() - started
    print(elapsed, count, requests, steps)


if __name__ == "__main__":
    main()
