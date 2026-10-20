# A call of an object, o(args), calls its class's __call__ by static dispatch, with positional,
# keyword and default arguments as a method call takes them: o a variable, a parameter, self, a
# field, a class attribute, an item, a call's result or a module's object; o that is None raises
# CPython's TypeError once the arguments are evaluated.
from dataclasses import dataclass
from typing import NamedTuple
import mods.calls
from mods.calls import hamming


def say(v: int) -> int:
    print("evaluated", v)
    return v


class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def __call__(self, x: int, y: int = 0, *, z: int = 1) -> int:
        return x * self.k + y * z


class Holder:
    k = Scale(10)

    def __init__(self, f: Scale) -> None:
        self.f = f
        self.g: Scale | None = None

    def apply(self, x: int) -> int:
        return self.f(x) + self.f(x, z=2, y=say(1))


class Fact:
    def __init__(self) -> None:
        self.one = self(1)  # (typed by what __call__ returns, as self.m(...) is by m)

    def __call__(self, n: int) -> int:
        return 1 if n <= 1 else n * self(n - 1)


class Make:
    def __call__(self, k: int) -> Scale:
        return Scale(k)


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str = "-") -> None:
        self.lines.append(line)


class Fail:
    def __call__(self, why: str) -> int:
        raise ValueError(why)


@dataclass
class Add:
    n: int

    def __call__(self, x: int) -> int:
        return x + self.n


class Mul(NamedTuple):
    n: int

    def __call__(self, x: int) -> int:
        return x * self.n


class Err(Exception):
    def __call__(self, x: int) -> str:
        return f"Err({x})"


def twice(f: Scale, x: int) -> int:
    return f(f(x))


def apply(f, x: int) -> int:
    return f(x)


def pick(i: int) -> Scale | None:
    print("pick", i)
    return Scale(i) if i > 0 else None


double = Scale(2)
print(double(5), double(5, 1), double(5, y=1, z=3), double(x=4))
print(twice(Scale(3), 2), apply(Mul(3), 4), apply(Add(1), 4))
h = Holder(Scale(5))
print(h.apply(2), h.f(3), Holder.k(1), h.k(2))
print([Scale(2), Scale(4)][1](10), {"a": Scale(9)}["a"](2), Scale(7)(1), Make()(3)(4))
print((Scale(1) if h.f.k > 5 else Scale(2))(3), (h.g or Scale(6))(1))
print(Fact()(10), Fact().one, Add(4)(1), Mul(5)(2), Err()(1))
log = Log()
print(log("a"))
log()
print(log.lines)
print([f(10) for f in [Scale(1), Scale(2)]], sum(f(1) for f in [Scale(3), Scale(4)]))
print(hamming("karolin", "kathrin"), mods.calls.hamming("abc", "abd"), hamming.similarity("abc", "abd"))
s = pick(3)
if s is not None:
    print(s(2))
try:
    Fail()("boom")
except ValueError as e:
    print("ValueError:", e)
try:
    print(pick(0)(say(1), z=say(2)))
except TypeError as e:
    print("TypeError:", e)
try:
    print(h.g(say(3)))
except TypeError as e:
    print("TypeError:", e)
try:
    print(mods.calls.missing("a", "b"))
except TypeError as e:
    print("TypeError:", e)
