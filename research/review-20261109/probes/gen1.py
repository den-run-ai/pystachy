from typing import Generator, Iterator
import itertools
import functools
import heapq
import bisect


def run(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


LOG: list[str] = []


def counter(n: int) -> Generator[int, int | None, str]:
    i = 0
    try:
        while i < n:
            try:
                got = yield i
            except ValueError as e:
                LOG.append(f"caught {e}")
                got = 100
            finally:
                LOG.append(f"fin{i}")
            if got is not None:
                i += got
            else:
                i += 1
    except GeneratorExit:
        LOG.append("exit")
        raise
    finally:
        LOG.append("outer")
    return "done"


def delegator(n: int) -> Generator[int, int | None, str]:
    r = yield from counter(n)
    LOG.append(f"sub returned {r}")
    r2 = yield from counter(2)
    return r + r2


def g1() -> list[str]:
    LOG.clear()
    g = delegator(5)
    out: list[int] = []
    out.append(next(g))
    out.append(g.send(2))
    out.append(g.throw(ValueError("boom")))
    for v in g:
        out.append(v)
    LOG.append(str(out))
    return LOG[:]


def g2() -> list[str]:
    LOG.clear()
    g = counter(10)
    next(g)
    next(g)
    g.close()
    g.close()
    try:
        next(g)
    except StopIteration:
        LOG.append("stopped")
    return LOG[:]


def fib() -> Iterator[int]:
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def take(n: int, it: Iterator[int]) -> list[int]:
    out: list[int] = []
    for x in it:
        if len(out) >= n:
            break
        out.append(x)
    return out


def chunks(xs: list[int], k: int) -> Iterator[list[int]]:
    for i in range(0, len(xs), k):
        yield xs[i : i + k]


def flatten(xss: list[list[int]]) -> Iterator[int]:
    for xs in xss:
        yield from xs


def primes() -> Iterator[int]:
    found: list[int] = []
    n = 2
    while True:
        if all(n % p for p in found if p * p <= n):
            found.append(n)
            yield n
        n += 1


def gen_with_return(flag: bool) -> Iterator[int]:
    yield 1
    if flag:
        return
    yield 2


def stopper() -> Iterator[int]:
    yield 1
    raise StopIteration


def reentrant() -> list[str]:
    out: list[str] = []
    holder: list[Iterator[int]] = []


    return out


def closure_gen() -> list[int]:
    fs = []
    for i in range(4):
        fs.append(lambda: i * 10)
    gs = [(lambda j: (lambda: j * 10))(i) for i in range(4)]
    return [f() for f in fs] + [g() for g in gs]


def genexp_late() -> list[int]:
    xs = [1, 2, 3]
    g = (x * 2 for x in xs)
    xs.append(4)
    return list(g)


def zip_uneven() -> list[str]:
    a = iter([1, 2, 3])
    b = iter(["a", "b"])
    out = [f"{x}{y}" for x, y in zip(a, b)]
    out.append(str(next(a, -1)))
    c = iter([1, 2, 3])
    d = iter(["a", "b"])
    out2 = [f"{y}{x}" for y, x in zip(d, c)]
    out2.append(str(next(c, -1)))
    return out + out2


def itertools_stuff() -> list[str]:
    out: list[str] = []
    out.append(str(list(itertools.islice(fib(), 5, 15, 3))))
    out.append(str(list(itertools.accumulate([1, 2, 3, 4]))))
    out.append(str(list(itertools.accumulate([1, 2, 3, 4], lambda a, b: a * b))))
    out.append(str(list(itertools.takewhile(lambda x: x < 20, primes()))))
    out.append(str(list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 1, 2]))))
    out.append(str(list(itertools.product([1, 2], [3, 4]))))
    out.append(str(list(itertools.permutations([1, 2, 3], 2))))
    out.append(str(list(itertools.combinations([1, 2, 3, 4], 2))))
    out.append(str(list(itertools.combinations_with_replacement([1, 2], 2))))
    out.append(str(list(itertools.zip_longest([1, 2, 3], [4], fillvalue=0))))
    out.append(str([(k, list(g)) for k, g in itertools.groupby([1, 1, 2, 3, 3, 3, 1])]))
    out.append(str([(k, len(list(g))) for k, g in itertools.groupby(sorted(["bb", "a", "ccc", "dd", "e"], key=len), key=len)]))
    out.append(str(list(itertools.repeat(7, 3))))
    out.append(str(list(itertools.islice(itertools.cycle([1, 2, 3]), 7))))
    out.append(str(list(itertools.islice(itertools.count(5, 3), 4))))
    out.append(str(list(itertools.starmap(lambda a, b: a - b, [(5, 1), (9, 3)]))))
    out.append(str(list(itertools.compress([1, 2, 3, 4], [1, 0, 1, 0]))))
    out.append(str(list(itertools.filterfalse(lambda x: x % 2, range(8)))))
    out.append(str(list(itertools.pairwise([1, 2, 3, 4]))))
    out.append(str(list(itertools.batched([1, 2, 3, 4, 5], 2))))
    out.append(str(functools.reduce(lambda a, b: a * 10 + b, [1, 2, 3, 4], 0)))
    out.append(str(functools.reduce(lambda a, b: a + b, ["a", "b", "c"])))
    return out


def heap_stuff() -> list[str]:
    out: list[str] = []
    h: list[tuple[int, str]] = []
    for i, w in enumerate(["pear", "apple", "fig", "kiwi", "banana", "date"]):
        heapq.heappush(h, (len(w), w))
    out.append(str([heapq.heappop(h) for _ in range(3)]))
    out.append(str(heapq.nlargest(2, [5, 1, 8, 3, 9, 2])))
    out.append(str(heapq.nsmallest(3, ["pear", "apple", "fig", "kiwi"], key=len)))
    xs = [9, 4, 7, 1, 8, 2]
    heapq.heapify(xs)
    out.append(str(xs))
    out.append(str(heapq.heappushpop(xs, 5)) + str(heapq.heapreplace(xs, 0)) + str(xs))
    ys = [1, 3, 3, 5, 9]
    out.append(str([bisect.bisect_left(ys, 3), bisect.bisect_right(ys, 3), bisect.bisect(ys, 0), bisect.bisect(ys, 10), bisect.bisect_left(ys, 4, 2, 4)]))
    bisect.insort(ys, 4)
    bisect.insort_left(ys, 3)
    out.append(str(ys))
    return out


def main() -> None:
    run("g1", g1)
    run("g2", g2)
    run("fib", lambda: take(10, fib()))
    run("chunks", lambda: list(chunks(list(range(10)), 3)))
    run("flatten", lambda: sum(flatten([[1, 2], [], [3]])))
    run("primes", lambda: take(10, primes()))
    run("ret", lambda: (list(gen_with_return(True)), list(gen_with_return(False))))
    run("stopper", lambda: list(stopper()))
    run("reentrant", reentrant)
    run("closure_gen", closure_gen)
    run("genexp_late", genexp_late)
    run("zip_uneven", zip_uneven)
    for line in itertools_stuff():
        print(line)
    for line in heap_stuff():
        print(line)


main()
