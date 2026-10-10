import sys

def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def shout(s: str) -> str:
    return s.upper() + "!"


def counts(s: str) -> dict[str, int]:
    d: dict[str, int] = {}
    for w in s.split():
        d[w] = d.get(w, 0) + 1
    return d


def check(n: int) -> int:
    if n < 0:
        raise ValueError("negative: " + str(n))
    return n * 2


def total(s: str) -> int:
    d = counts(s)
    t = 0
    for k in d:
        t += d[k] * len(k)
    return t


def guarded(n: int) -> int:
    try:
        return check(n)
    except KeyError:
        return -1


CACHE: dict[str, int] = {}


def remember(s: str) -> int:
    CACHE[s + "#" + str(len(CACHE))] = len(s)
    return len(CACHE)


def hello(s: str) -> None:
    print("pys:", s)


def inc(n: int) -> int:
    return n + 1


def strlen(s: str) -> int:
    return len(s)


class Boom(Exception):
    pass


def bye(n: int) -> None:
    sys.exit(n)


def boom(n: int) -> int:
    if n > 0:
        raise Boom("boom " + str(n))
    return n


def key(s: str) -> int:
    d = counts(s)
    return d["missing"]
