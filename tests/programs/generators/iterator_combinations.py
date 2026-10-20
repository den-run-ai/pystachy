# Iterator classes (#477) with star unpacking (#474), slice assignment (#473), comprehensions of
# several for clauses (#472), collections (#470) and str.format() (#476): CPython 3.13 calls
# iter() of the iterator again where it takes list() of it (UNPACK_EX, PySequence_Fast) and in
# every for clause of a comprehension.
from collections import Counter, OrderedDict, defaultdict, deque


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self):
        print("iter", self.n)
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


def main() -> None:
    a, *b = Count(4)
    print(a, b)
    print([*Count(3), 0, *Count(2)])
    xs = list(range(8))
    xs[::2] = Count(4)
    print(xs)
    xs[1:3] = Count(5)
    print(xs)
    print([(i, j) for i in Count(2) for j in Count(i + 1)])
    print({i: j for i in Count(2) for j in Count(2)})
    print({i * j for i in Count(3) if i > 1 for j in Count(2)})
    tot = 0
    print([tot := tot + v for v in Count(3)], tot)
    c = Counter(Count(3))
    print(sorted(c.items()))
    d = deque(Count(3))
    print(d, list(reversed(d)))
    od = OrderedDict([(k, k * k) for k in Count(3)])
    print(od, list(reversed(od)))
    dd: defaultdict[int, list[int]] = defaultdict(list)
    for k in Count(3):
        dd[k % 2].append(k)
    print(sorted(dd.items()))
    it = iter(Count(3))
    print("{} {}".format(next(it), next(it)), next(it, -1), next(it, -1))
    print(tuple(Count(3)), sum(Count(4)), max(Count(3)), sorted(Count(3), reverse=True))
    q = deque([1, 2, 3])
    try:
        for v in q:
            q.append(v)
    except RuntimeError as e:
        print("RuntimeError", e)
    r = deque([1, 2, 3])
    seen = []
    for v in r:
        seen.append(v)
    print(seen)


main()
