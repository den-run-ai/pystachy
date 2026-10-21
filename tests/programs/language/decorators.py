# Decorators on defs run when the def statement does, as in CPython: the decorator expressions
# are evaluated from the top, then the defaults, then each decorator is called, from the bottom,
# with what the one below gave, and the def's name binds the last result, whatever it is
from typing import Callable, final


class Parser:
    def __init__(self, fn: Callable[[str, int], int]) -> None:
        self.fn = fn

    def __call__(self, s: str, i: int) -> int:
        return self.fn(s, i)

    def then(self, other: "Parser") -> "Parser":
        def both(s: str, i: int) -> int:
            j = self(s, i)
            return -1 if j < 0 else other(s, j)
        return Parser(both)


@Parser
def eof(s: str, i: int) -> int:
    return i if i >= len(s) else -1


def lit(c: str) -> Parser:
    @Parser
    def p(s: str, i: int) -> int:
        return i + 1 if i < len(s) and s[i] == c else -1
    return p


ab = lit("a").then(lit("b")).then(eof)
print(isinstance(eof, Parser), eof("ab", 2), eof("ab", 1), ab("ab", 0), ab("abc", 0), ab("b", 0))


def use() -> int:
    return inc(5)  # (inc: what twice gave, once the def below has run)


try:
    print(use())
except NameError as e:
    print("NameError:", e)


def twice(f):
    def g(x):
        return f(f(x))
    return g


@twice
def inc(x):
    return x + 1


print(use(), inc(1), inc(2.5))


def value(f):
    return f()


@value
def answer() -> int:
    return 42


print(answer + 1)


def note(msg: str) -> str:
    print("eval", msg)
    return msg


def mark(label):
    print("deco", label)

    def d(f):
        print("apply", label)
        return f
    return d


@mark("a")
@mark("b")
def k(x=note("default")):
    return x


print(k(), k("given"))

registry: list[str] = []


def register(f):
    registry.append(f"{len(registry)}")
    return f


@register
@register
def both(a, b=2):
    return a * 10 + b


print(registry, both(1), both(1, b=3), both(b=4, a=5))


def trace(f):
    def w(x):
        print("call", x)
        return f(x)
    return w


@trace
def ident(x):
    return x


print(ident(1), ident("s"))


def maybe(flag: bool) -> int:
    if flag:
        d = twice

    @d
    def h(x):
        return x * 3
    return h(1)


print(maybe(True))
try:
    maybe(False)
except UnboundLocalError as e:
    print("UnboundLocalError:", e)


def counter(start: int) -> Callable[[], int]:
    n = [start]

    @value
    def first() -> int:
        n[0] += 1
        return n[0]

    def nxt() -> int:
        n[0] += first
        return n[0]
    return nxt


c = counter(1)
print(c(), c(), c())


def shadowed() -> int:
    # (a local decorator named as a typing one is the local: CPython calls it)
    def final(f):
        def g():
            return 42
        return g

    @final
    def h() -> int:
        return 1

    return h()


def typed() -> int:
    @final
    def k() -> int:
        return 7

    return k()


print(shadowed(), typed())
