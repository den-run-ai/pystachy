# Range lengths are unsigned: next() must work above the signed 64-bit length limit.
lo = -9223372036854775807 - 1
hi = 9223372036854775807

def first(start: int, stop: int, step: int) -> None:
    it = iter(range(start, stop, step))
    print(next(it), next(it), next(it))

first(lo, -1, 1)  # INT64_MAX items
first(lo, 0, 1)   # INT64_MAX + 1: decrement crosses the sign bit immediately
first(lo, 1, 1)   # INT64_MAX + 2: the second decrement crosses the sign bit
first(lo, hi, 1)  # UINT64_MAX items
first(0, lo, -1)
first(1, lo, -1)
first(hi, lo, -1)

# Do not compute an overflowing successor after the final item.
a = iter(range(hi - 1, hi, hi))
print(next(a), next(a, 42), next(a, 42))
b = iter(range(lo + 1, lo, lo))
print(next(b), next(b, 42), next(b, 42))
c = iter(range(hi, lo, lo))
print(next(c), next(c), next(c, 42))
d = iter(range(0))
print(next(d, 42), next(d, 42))
