# Encode then decode a cache-like stream: per record, a tag, three ints of mixed sizes, a
# short str, a float and a bool; then extract 100000 nested symbols in turn.
import sys
import time
from librt.internal import (ReadBuffer, WriteBuffer, extract_symbol, read_bool, read_float, read_int,
                            read_str, read_tag, write_bool, write_float, write_int, write_str, write_tag)


def run(n: int) -> int:
    names = [f"mod{i}.Name{i % 97}" for i in range(1000)]
    w = WriteBuffer()
    for i in range(n):
        write_tag(w, i & 127)
        write_int(w, i % 100)
        write_int(w, i * 37)
        write_int(w, i * 1000003)
        write_str(w, names[i % 1000])
        write_float(w, i * 0.5)
        write_bool(w, i % 3 == 0)
    data = w.getvalue()
    r = ReadBuffer(data)
    total = 0
    for i in range(n):
        total += read_tag(r) + read_int(r) + read_int(r) % 7 + read_int(r) % 11 + len(read_str(r))
        total += int(read_float(r)) % 5 + (1 if read_bool(r) else 0)
    sw = WriteBuffer()
    for i in range(100000):
        write_tag(sw, 4)
        write_str(sw, names[i % 1000])
        write_tag(sw, 60)
        write_tag(sw, 3)
        write_int(sw, i)
        write_tag(sw, 255)
        write_tag(sw, 255)
    sr = ReadBuffer(sw.getvalue())
    syms = 0
    for i in range(100000):
        syms += len(extract_symbol(sr))
    return total + len(data) + syms


t = time.perf_counter()
print(run(300000))
print(f"{time.perf_counter() - t:.3f}", file=sys.stderr)
