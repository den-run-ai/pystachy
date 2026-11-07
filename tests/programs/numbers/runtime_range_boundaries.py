# Runtime range arithmetic keeps unsigned distances/counts even across INT64_MIN.
lo = -9223372036854775807 - 1
hi = 9223372036854775807
ends = [lo, lo + 1, -123, -1, 0, 1, 123, hi - 1, hi]
steps = [lo, -hi, -7, -1, 1, 7, hi]
lengths = 0
oversized = 0
nonempty = 0
hits = 0
for a in ends:
    for b in ends:
        for step in steps:
            r = range(a, b, step)
            nonempty += int(bool(r))
            try:
                lengths += len(r) % 997
            except OverflowError:
                oversized += 1
            for x in ends:
                hits += int(x in r)
                assert (x in r) == (x in range(a, b, step))
print(lengths, oversized, nonempty, hits)
for a, b, step in [(lo, hi, 1), (hi, lo, -1), (hi, lo, lo), (lo, hi, hi)]:
    r = range(a, b, step)
    print(r[0], r[-1], r[1])
try:
    print(len(range(0, 0, 0)))
except ValueError as error:
    print(error)
try:
    print(0 in range(0, 0, 0))
except ValueError as error:
    print(error)
