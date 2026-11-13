# A test of an attribute narrows its reads only while nothing can have stored the attribute:
# each read here follows something that stored it, and must give what CPython's second read
# of the attribute gives.
from typing import Iterator


class Node:
    def name(self) -> str:
        return "node"


class Info(Node):
    def name(self) -> str:
        return "info"


class Var(Node):
    def name(self) -> str:
        return "var"


class Ref:
    shared: int | str = 1

    def __init__(self, node: Node | None) -> None:
        self.node = node
        self.value: int | str = 0
        self.count: int | None = None

    def swap(self) -> None:
        self.node = Var()
        self.value = "swapped"
        self.count = None

    def __eq__(self, other: object) -> bool:
        self.swap()
        return True

    def __str__(self) -> str:
        self.swap()
        return "ref"

    @property
    def moving(self) -> Node:
        self.swap()
        return Var()


class Holder:
    def __init__(self, ref: Ref) -> None:
        self.ref = ref


def swap(e: Ref) -> None:
    e.node = Var()
    e.value = "swapped"
    e.count = None


def fresh() -> Ref:
    r = Ref(Info())
    r.value = 7
    r.count = 3
    return r


def stored(e: Ref, v: Node) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        e.node = v
        e.value = "direct"
        return f"{e.node.name()} {e.value}"
    return "?"


def callee(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        swap(e)
        return f"{e.node.name()} {e.value}"
    return "?"


def method(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        e.swap()
        return f"{e.node.name()} {e.value}"
    return "?"


def alias(e: Ref, v: Node) -> str:
    other = e
    if isinstance(e.node, Info) and isinstance(e.value, int):
        other.node = v
        other.value = "alias"
        return f"{e.node.name()} {e.value}"
    return "?"


def second(e: Ref, other: Ref, v: Node) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        other.node = v
        other.value = "second"
        return f"{e.node.name()} {e.value}"
    return "?"


def rebound(e: Ref, other: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        e = other
        return f"{e.node.name() if e.node is not None else 'none'} {e.value}"
    return "?"


def prefix(h: Holder, other: Ref) -> str:
    if isinstance(h.ref.node, Info) and isinstance(h.ref.value, int):
        h.ref = other
        return f"{h.ref.node.name() if h.ref.node is not None else 'none'} {h.ref.value}"
    return "?"


def equality(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        same = e == e
        return f"{same} {e.node.name()} {e.value}"
    return "?"


def text(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        shown = str(e)
        return f"{shown} {e.node.name()} {e.value}"
    return "?"


def prop(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        moved = e.moving
        return f"{moved.name()} {e.node.name()} {e.value}"
    return "?"


def looped(e: Ref) -> str:
    out: list[str] = []
    if isinstance(e.node, Info) and isinstance(e.value, int):
        for i in range(2):
            out.append(f"{e.node.name() if e.node is not None else 'none'} {e.value}")
            swap(e)
    return ", ".join(out)


def gen(e: Ref) -> Iterator[int]:
    yield 1
    swap(e)
    yield 2


def resumed(e: Ref) -> str:
    g = gen(e)
    next(g)
    if isinstance(e.node, Info) and isinstance(e.value, int):
        next(g)
        return f"{e.node.name()} {e.value}"
    return "?"


def closure(e: Ref) -> str:
    def change() -> None:
        e.node = Var()
        e.value = "closure"

    if isinstance(e.node, Info) and isinstance(e.value, int):
        change()
        return f"{e.node.name()} {e.value}"
    return "?"


def shortcut(e: Ref, flag: bool) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        done = flag and e.swap() is None
        return f"{done} {e.node.name()} {e.value}"
    return "?"


def ternary(e: Ref, flag: bool) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        n = 1 if flag else len(str(e))
        return f"{n} {e.node.name()} {e.value}"
    return "?"


def comprehension(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        seen = [str(x) for x in [e]]
        return f"{seen} {e.node.name()} {e.value}"
    return "?"


def handler(e: Ref, xs: list[int]) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        try:
            swap(e)
            xs[5] += 1
        except IndexError:
            return f"caught {e.node.name()} {e.value}"
    return "?"


def optional(e: Ref) -> str:
    if e.count is not None:
        swap(e)
        return f"{e.count}"
    return "?"


def class_attribute(e: Ref) -> str:
    if isinstance(e.shared, int):
        Ref.shared = "all"
        return f"{e.shared}"
    return "?"


def message(e: Ref) -> str:
    assert isinstance(e.node, Info), str(e)
    return e.node.name()


def raised(e: Ref, flag: bool) -> str:
    if isinstance(e.value, int):
        try:
            if flag:
                e.value = "raised"
                raise ValueError("x")
        except ValueError:
            return f"{e.value}"
    return "?"


def returned(e: Ref, flag: bool, out: list[str]) -> str:
    if isinstance(e.value, int):
        try:
            if flag:
                e.value = "returned"
                return "early"
        finally:
            out.append(f"{e.value}")
    return "late"


def broke(e: Ref, flag: bool) -> str:
    if isinstance(e.value, int):
        while True:
            if flag:
                e.value = "broke"
                break
            break
        return f"{e.value}"
    return "?"


def continued(e: Ref) -> str:
    out: list[str] = []
    for i in range(2):
        if isinstance(e.value, int):
            if i == 0:
                e.value = "continued"
                continue
        out.append(f"{e.value}")
    return ",".join(out)


def asserting(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        try:
            assert e.value > 100, str(e)
        except AssertionError:
            return f"{e.node.name()} {e.value}"
    return "?"


def branch(e: Ref, flag: bool) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        if flag:
            swap(e)
        return f"{e.node.name()} {e.value}"
    return "?"


print(stored(fresh(), Var()))
print(callee(fresh()))
print(method(fresh()))
print(alias(fresh(), Var()))
r = fresh()
print(second(r, r, Var()))
print(rebound(fresh(), Ref(None)))
print(prefix(Holder(fresh()), Ref(None)))
print(equality(fresh()))
print(text(fresh()))
print(prop(fresh()))
print(looped(fresh()))
print(resumed(fresh()))
print(closure(fresh()))
print(shortcut(fresh(), True), shortcut(fresh(), False))
print(ternary(fresh(), True), ternary(fresh(), False))
print(comprehension(fresh()))
print(handler(fresh(), [1]))
print(optional(fresh()))
print(branch(fresh(), True), branch(fresh(), False))
print(class_attribute(fresh()), message(fresh()))
print(raised(fresh(), True), raised(fresh(), False), broke(fresh(), True), broke(fresh(), False))
seen: list[str] = []
print(returned(fresh(), True, seen), returned(fresh(), False, seen), seen, continued(fresh()), asserting(fresh()))
