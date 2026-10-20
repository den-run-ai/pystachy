# Suspended generators keep what they hold alive (#490): fifty generators, each holding a list
# and a dict in its frame, are resumed in turn while the program allocates garbage between; the
# frames come from the collector's scanned heap.
from collections.abc import Iterator


def holder(n: int, k: int) -> Iterator[int]:
    data = [i * 3 + k for i in range(n)]
    names: dict[str, int] = {}
    for i in range(n):
        names[str(i)] = i
    tags = ["t" + str(k)] * 3
    for i in range(n):
        yield data[i] + names[str(i)] + len(tags[i % 3])


def step(g: Iterator[int]) -> int:
    for v in g:
        return v
    return -1


gens = [holder(100, k) for k in range(50)]
firsts = [step(g) for g in gens]
garbage = 0
for r in range(40):
    junk = [str(i) * 3 for i in range(500)]
    garbage += len(junk)
    for g in gens:
        step(g)
total = 0
for g in gens:
    for v in g:
        total += v
print(sum(firsts), total, garbage)
