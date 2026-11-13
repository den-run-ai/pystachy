# How programs use an executor: as a parameter, in a call that submits again, with futures in
# annotated lists, generator expressions and dicts, closures, partial() and unpacked arguments
import concurrent.futures
import functools
from concurrent.futures import Future, ThreadPoolExecutor, as_completed, wait


def scale(x: int, k: int = 2) -> int:
    return x * k


def run_all(pool: ThreadPoolExecutor, xs: list[int]) -> list[int]:
    return list(pool.map(scale, xs))


def run_one(pool: ThreadPoolExecutor, x: int) -> "Future[int]":
    return pool.submit(scale, x, k=3)


def nested(pool: ThreadPoolExecutor, x: int) -> int:
    return pool.submit(scale, x).result() + 1


def words(n: int) -> dict[str, int]:
    return {"w%d" % i: i for i in range(n)}


def gen(n: int):
    for i in range(n):
        yield i


def main() -> None:
    with ThreadPoolExecutor(max_workers=3) as pool:
        print(run_all(pool, [1, 2, 3]), run_one(pool, 5).result())
        print(pool.submit(nested, pool, 4).result())
        fs: list[concurrent.futures.Future[int]] = [pool.submit(scale, i) for i in range(3)]
        print(sorted(f.result() for f in as_completed(fs)))
        print(sorted(f.result() for f in as_completed(pool.submit(scale, x) for x in (7, 8))))
        done, pending = wait(pool.submit(scale, x) for x in [9, 10])
        print(sorted(f.result() for f in done), len(pending))
        print(pool.submit(words, 2).result())
        base = 100

        def shifted(x: int) -> int:
            return x + base

        print(pool.submit(shifted, 1).result(), list(pool.map(shifted, gen(3))))
        args = (6, 7)
        print(pool.submit(scale, *args).result())
        print(pool.submit(functools.partial(scale, k=5), 2).result())
        results = [f.result() for f in [pool.submit(pow, 2, n) for n in range(4)]]
        print(results)
        t = pool.submit(lambda: (1, "a"))
        print(t.result()[1])


main()
