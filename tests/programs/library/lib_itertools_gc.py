# itertools' generators keep what they hold alive while suspended (lib/_pystachy_itertools.py):
# pipelines over strings made as the program runs, resumed in turn while the program allocates
# garbage between (with PYSTACHY_GC_STRESS_PROGRAM, a collection at every allocation): tee's
# links, groupby's shared state and groups, cycle's saved items, the combinatoric pools and
# fifty suspended iterators at once.
from itertools import (accumulate, batched, chain, combinations, count, cycle, groupby, islice, pairwise, permutations,
                       product, tee, zip_longest)
from collections.abc import Iterator


def words(n: int) -> Iterator[str]:
    for i in range(n):
        yield "w" + str(i) * 3


def churn(k: int) -> int:
    junk: list[list[str]] = []
    for i in range(k):
        junk.append([str(i) + "j"] * 4)
    return len(junk)


total = 0
for a, b in pairwise(words(120)):
    churn(3)
    total += len(a) + len(b)
print("pairwise", total)

t1, t2 = tee(words(130))
first = list(islice(t1, 70))
churn(40)
print("tee", len(first), first[-1], sum(len(w) for w in t2), len(list(t1)))

keyed = [str(i // 4) + ":" + str(i) for i in range(40)]
sizes: list[str] = []
for k, g in groupby(keyed, lambda s: s.split(":")[0]):
    churn(2)
    sizes.append(k + "=" + ",".join(g))
print("groupby", len(sizes), sizes[0], sizes[-1])

cyc = cycle(words(5))
churn(20)
print("cycle", list(islice(cyc, 12))[-3:])

print("product", sum(len("".join(t)) for t in product([str(i) * 2 for i in range(4)], repeat=3)))
pools = [str(i) + "p" for i in range(7)]
n = 0
for c in combinations(pools, 3):
    churn(1)
    n += len(c[0] + c[1] + c[2])
print("combinations", n, len(list(permutations(pools[:5], 3))))
print("accumulate", list(accumulate(words(6)))[-1])
print("chain", len(list(chain.from_iterable([w] * 3 for w in words(30)))))
print("batched", [b[-1] for b in batched(words(20), 6)])
print("zip_longest", list(zip_longest(words(3), (w.upper() for w in words(5)), fillvalue="-"))[-1])

suspended = [islice(cycle([str(i) + "x", str(i) + "y"]), 7) for i in range(50)]
counters = [zip_longest(count(i), words(3)) for i in range(50)]
out: list[str] = []
for step in range(7):
    churn(5)
    for it in suspended:
        for v in it:
            out.append(v)
            break
print("suspended", len(out), out[0], out[-1])
print("counters", sum(len(list(islice(c, 4))) for c in counters))
