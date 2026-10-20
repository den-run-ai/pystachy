# Exception classes with defaults and keyword-only parameters, as fields and Optional values,
# passed to a template, raised from __init__, and the name of an except clause bound where a
# parameter or a global of another type has it (the clause unbinds both, as CPython deletes it).
from typing import Optional


class Base(Exception):
    def __init__(self, msg: str, code: int = 1, *, hint: str = ""):
        super().__init__(msg, code)
        self.code = code
        self.hint = hint
        if code < 0:
            raise ValueError("negative code")

    def describe(self) -> str:
        return f"{self} [{self.code}] {self.hint}"


class Mid(Base):
    def describe2(self) -> str:
        return "mid " + super().describe()


class Leaf(Mid):
    items: list[int] = []

    def __init__(self, n: int):
        super().__init__(f"leaf {n}", n, hint="h")
        self.cause: Base | None = None


class Holder:
    def __init__(self):
        self.err: Optional[Base] = None
        self.errs: list[Base] = []


def make(n: int) -> Base:
    if n > 2:
        return Leaf(n)
    return Base("made", n)


def show(e):
    print("template:", e, repr(e))


h = Holder()
for n in [0, 1, 3]:
    h.errs.append(make(n))
h.err = h.errs[-1]
print(h.err, h.errs)
if h.err is not None:
    print(h.err.describe())
print(Base("a").describe(), Base("b", 5, hint="x").describe(), Mid("m").describe2())
l = Leaf(4)
l.items.append(1)
Leaf(5).items.append(2)
print(l.items, l.cause, l.describe2())
l.cause = Base("root")
print(l.cause)
try:
    Base("bad", -1)
except ValueError as e:
    print("init raised:", e)
show(Leaf(7))
show(ValueError("v"))
g = 5


def f(e: int) -> None:
    try:
        raise Base("p", e)
    except Base as e:
        print("param shadowed:", e.code)
    try:
        print(e)
    except UnboundLocalError as u:
        print("unbound:", u)


f(9)
try:
    raise Mid("mod")
except Mid as e:
    print("global shadow:", e.code)
try:
    print(e)
except NameError as x:
    print("name error:", x)
