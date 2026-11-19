# A test of an attribute narrows the reads of that attribute that follow it, as a test of a
# local narrows the local, until something may store the attribute: mypy's member narrowing,
# if isinstance(e.node, TypeInfo): e.node.fullname.
from typing import Callable


class Node:
    pass


class Info(Node):
    def __init__(self, fullname: str) -> None:
        self.fullname = fullname
        self.final = False

    def short(self) -> str:
        return self.fullname[self.fullname.rfind(".") + 1 :]


class Var(Node):
    def __init__(self, type_name: str | None) -> None:
        self.type_name = type_name


class Ref:
    def __init__(self, node: Node | None) -> None:
        self.node = node
        self.value: int | str = 0
        self.count: int | None = None
        self.label: str | None = None
        self.seen = 0


class Holder:
    def __init__(self, ref: Ref) -> None:
        self.ref = ref
        self.filter: bool | Callable[[str], bool] = False

    def passes(self, s: str) -> bool:
        if isinstance(self.filter, bool):
            ok = self.filter
        elif callable(self.filter):
            ok = self.filter(s)
        else:
            raise AssertionError(f"invalid filter: {type(self.filter)}")
        return ok

    def name(self) -> str:
        if isinstance(self.ref.node, Info):
            return self.ref.node.fullname
        return "?"


def takes(info: Info) -> str:
    return "<" + info.short() + ">"


def describe(e: Ref) -> str:
    if isinstance(e.node, Info):
        return e.node.fullname
    return "not a type"


def guarded(e: Ref) -> str:
    if not isinstance(e.node, Info):
        return "other " + str(len(str(e.seen)))
    name = e.node.fullname
    return name[name.rfind(".") + 1 :] + takes(e.node)


def kinds(e: Ref) -> str:
    if isinstance(e.node, Info):
        return "info " + e.node.fullname
    elif isinstance(e.node, Var):
        return "var " + (e.node.type_name if e.node.type_name is not None else "untyped")
    elif e.node is None:
        return "none"
    else:
        return "node"


def both(x: object) -> str:
    if isinstance(x, Ref) and isinstance(x.node, Info):
        return x.node.fullname + ("!" if x.node.final else "")
    return "no"


def ternary(e: Ref) -> str:
    return e.node.short() if isinstance(e.node, Info) else "none" if e.node is None else "node"


def number(e: Ref) -> int:
    if isinstance(e.value, int):
        return e.value + 1
    return len(e.value)


def counted(e: Ref) -> int:
    if e.count is not None:
        e.seen = e.count + 1
        return e.count * 2 + e.seen
    return -1


def labelled(e: Ref) -> str:
    if e.label:
        return e.label.upper()
    return "(none)"


def asserted(e: Ref) -> str:
    assert isinstance(e.node, Info)
    info = e.node
    info.final = True
    return info.fullname


def nested(h: Holder) -> str:
    if isinstance(h.ref.node, Var) and h.ref.node.type_name is not None:
        return h.ref.node.type_name + " " + str(len(h.ref.node.type_name))
    return "-"


def other_stores(e: Ref) -> str:
    if isinstance(e.node, Info) and isinstance(e.value, int):
        e.seen = e.value + 1
        e.label = e.node.fullname
        total = e.value + e.seen
        return f"{e.node.fullname} {total} {e.label}"
    return "?"


def branches(e: Ref, flag: bool) -> str:
    if isinstance(e.node, Info):
        if flag:
            return "flag " + takes(e.node)
        else:
            s = e.node.fullname
        return s + "/" + takes(e.node)
    return "?"


def looped(refs: list[Ref]) -> list[str]:
    out: list[str] = []
    for e in refs:
        if isinstance(e.node, Info):
            out.append(e.node.short())
    return out + [e.node.fullname for e in refs if isinstance(e.node, Info)]


def waits(e: Ref) -> int:
    n = 0
    while e.count is not None and e.count > n:
        n += e.count
    return n


int_ref = Ref(Info("builtins.int"))
int_ref.count = 3
int_ref.label = "x"
str_ref = Ref(Var("str"))
str_ref.value = "four"
none_ref = Ref(None)
refs = [int_ref, str_ref, none_ref, Ref(Var(None)), Ref(Node())]
print([describe(e) for e in refs])
print([guarded(e) for e in refs])
print([kinds(e) for e in refs])
print(both(int_ref), both(str_ref), both(3))
print([ternary(e) for e in refs])
print([number(e) for e in refs], [counted(e) for e in refs], [labelled(e) for e in refs])
print(asserted(int_ref), both(int_ref))
print([nested(Holder(e)) for e in refs])
print(other_stores(int_ref), int_ref.seen, int_ref.label)
print(branches(int_ref, True), branches(int_ref, False), branches(none_ref, True))
print(looped(refs), waits(int_ref), waits(none_ref))
h = Holder(int_ref)
print(h.name(), h.passes("a"))
h.filter = True
print(h.passes("a"))
h.filter = lambda s: len(s) > 1
print(h.passes("a"), h.passes("ab"))
