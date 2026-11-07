# Structural probe and optional timing for numeric list reads. The range stop
# measures xs; sparse_gather's xs[column] needs a separate data-dependent check.
# CPython/compiled checksum: python3 bench/list_reads.py 1
# Timing: ./pystachy run bench/list_reads.py 10000 --time
import sys
import time


def stride_sum(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs), 2):
        total += xs[i]
    return total


def dot_zip(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    for x, y in zip(xs, ys):
        total += x * y
    return total


def sparse_gather(xs: list[float], columns: list[int]) -> float:
    total = 0.0
    for column in columns:
        total += xs[column]
    return total


xs = [float(i % 16) * 0.25 for i in range(2048)]
ys = [float(i % 8) * 0.125 for i in range(2048)]
columns = [(i * 17) % len(xs) for i in range(4096)]
rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1
start = time.process_time()
checksum = 0.0
for _ in range(rounds):
    checksum += stride_sum(xs) + dot_zip(xs, ys) + sparse_gather(xs, columns)
print(checksum)
if "--time" in sys.argv:
    print(time.process_time() - start)
