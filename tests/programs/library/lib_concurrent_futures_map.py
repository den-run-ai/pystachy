# Executor.map(): the results in the order of the arguments, over one to four iterables (as
# zip() pairs them), with timeout and chunksize; map() submits every call at once, and the
# iterator raises a call's exception where its result would be
from concurrent.futures import ThreadPoolExecutor


def square(n: int) -> int:
    return n * n


def add(a: int, b: int) -> int:
    return a + b


def volume(a: int, b: int, c: int) -> str:
    return "%dx%dx%d" % (a, b, c)


def total(a: int, b: int, c: int, d: int) -> int:
    return a + b + c + d


def one() -> int:
    return 1


def check(n: int) -> str:
    if n == 2:
        raise ValueError("two")
    return "ok%d" % n


def note(n: int) -> None:
    pass


with ThreadPoolExecutor(max_workers=4) as pool:
    print(list(pool.map(square, [1, 2, 3])), list(pool.map(square, range(4))))
    print(list(pool.map(add, [1, 2, 3], [10, 20, 30, 40])))
    print(list(pool.map(volume, [1, 2], (3, 4), range(5, 9))))
    print(list(pool.map(total, [1, 2], [10, 20], [100, 200], [1000, 2000])))
    print(list(pool.map(one)))
    empty: list[int] = []
    print(list(pool.map(square, empty)))
    print(list(pool.map(square, (5, 6), timeout=5)), list(pool.map(square, [7], chunksize=3)))
    print(sum(pool.map(square, [1, 2, 3])), sorted(pool.map(len, {"a": 1, "bcd": 2})))
    for r in pool.map(str.upper, ["a", "b"]):
        print(r)
    print(list(pool.map(lambda x: x + 1, [1, 2])))
    it = pool.map(check, [0, 1, 2, 3])
    print(next(it), next(it))
    try:
        next(it)
    except ValueError as e:
        print("ValueError:", e)
    try:
        next(it)
    except StopIteration:
        print("StopIteration")
    n = 0
    for _ in pool.map(note, [1, 2]):
        n += 1
    print(n)
try:
    pool.map(square, [1])
except RuntimeError as e:
    print("RuntimeError:", e)
