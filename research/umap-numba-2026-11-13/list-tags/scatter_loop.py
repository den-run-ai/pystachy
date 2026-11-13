"""Scatter-add and histogram loops: item stores through computed indexes, between reads of other lists."""
import sys

rounds = int(sys.argv[1])
n = 1000
xs = [(i % 97) * 0.25 for i in range(n)]
idx = [(i * 7919) % n for i in range(n)]
bins = [(i * 31) % 64 for i in range(n)]
out = [0.0] * n
counts = [0] * 64
for r in range(rounds):
    for i in range(len(idx)):
        out[idx[i]] += xs[i]
        counts[bins[i]] += 1
print(repr(sum(out)), sum(counts))
