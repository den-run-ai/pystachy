# Upstream mypy.cache's typed helpers at scale: 100,000 error records and lists written and read.
import sys
import time
from librt.internal import ReadBuffer, WriteBuffer
from mypy.cache import (read_errors, read_int_list, read_str_list, write_errors, write_int_list, write_str_list)


def run(n: int) -> int:
    errs: list[tuple[str | None, int, int, int, int, str, str, str | None]] = [("pkg/mod%d.py" % (i % 50), i, i % 80, i + 1, i % 80 + 5, "error", f"Name \"x{i}\" is not defined", "name-defined") for i in range(1000)]
    w = WriteBuffer()
    for i in range(n // 1000):
        write_errors(w, errs)
        write_int_list(w, list(range(i, i + 100)))
        write_str_list(w, [e[6] for e in errs[:50]])
    data = w.getvalue()
    r = ReadBuffer(data)
    total = len(data)
    for i in range(n // 1000):
        total += len(read_errors(r)) + sum(read_int_list(r)) + len(read_str_list(r))
    return total


t = time.perf_counter()
print(run(100000))
print(f"{time.perf_counter() - t:.3f}", file=sys.stderr)
