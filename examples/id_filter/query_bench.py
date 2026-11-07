"""Native-capable worker for bench.py; see README for the measured contract."""

import sys
import time

from idset import IdSet, from_ids


def inputs(capacity: int, stride: int) -> tuple[list[int], list[int]]:
    if capacity < 0 or stride < 1:
        raise ValueError("capacity must be nonnegative and stride positive")
    # Shuffle ID ranks before sampling so density is not a low-bit hash pattern.
    order = list(range(capacity))
    state = 7
    for i in range(capacity - 1, 0, -1):
        state = (state * 48271) % 2147483647
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    left: list[int] = []
    right: list[int] = []
    for rank in range(0, capacity, stride):
        left.append(order[rank])
        selected = rank + (len(left) - 1) % 2
        if selected < capacity:
            right.append(order[selected])
    return left, right


def set_count(left: set[int], right: set[int]) -> int:
    # Count without allocating the intersection; scan the smaller operand.
    if len(left) > len(right):
        left, right = right, left
    total = 0
    for value in left:
        if value in right:
            total += 1
    return total


def query_bitmap(left: IdSet, right: IdSet, ids: list[int], repeats: int) -> int:
    total = 0
    for i in range(repeats):
        if ids:
            value = ids[i % len(ids)]
            if (i // len(ids)) % 2:
                left.add(value)
            else:
                left.discard(value)
        total += left.intersection_count(right)
    return total


def query_sets(left: set[int], right: set[int], ids: list[int], repeats: int,
               materialize: bool) -> int:
    total = 0
    for i in range(repeats):
        if ids:
            value = ids[i % len(ids)]
            if (i // len(ids)) % 2:
                left.add(value)
            else:
                left.discard(value)
        if materialize:
            total += len(left & right)
        else:
            total += set_count(left, right)
    return total


def main() -> None:
    if len(sys.argv) != 5:
        raise ValueError("usage: query_bench.py bitmap|set-scan|set-intersection CAPACITY STRIDE REPEATS")
    mode = sys.argv[1]
    capacity = int(sys.argv[2])
    stride = int(sys.argv[3])
    repeats = int(sys.argv[4])
    if mode not in ["bitmap", "set-scan", "set-intersection"] or repeats < 0:
        raise ValueError("unknown mode or negative repetitions")
    values, selected = inputs(capacity, stride)
    start = time.perf_counter()
    if mode == "bitmap":
        left = from_ids(capacity, values)
        right = from_ids(capacity, selected)
        built = time.perf_counter()
        checksum = query_bitmap(left, right, values, repeats)
        done = time.perf_counter()
        result = left.ids()
    else:
        a = set(values)
        b = set(selected)
        built = time.perf_counter()
        checksum = query_sets(a, b, values, repeats, mode == "set-intersection")
        done = time.perf_counter()
        result = sorted(a)
    # Full final IDs plus a checksum: witness serialization is outside both timers.
    print(checksum, result)
    print(built - start, done - built)


if __name__ == "__main__":
    main()
