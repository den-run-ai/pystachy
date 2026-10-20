# Template corner cases: hasattr of object attributes, of the builtin types' methods and of
# fields __init__ may leave unassigned; isinstance with a class among other types and with
# X | Y; a static operand of and/or is the value; a None argument rebound by the
# empty-container idiom; a function that falls off its end returns None for objects; code
# after a return or a failing assert is not compiled for the types that make it dead; while
# on None; default values are evaluated once, when the def runs.
import sys


class C:
    def __init__(self, v: int):
        self.v = v

    def __repr__(self) -> str:
        return f"C({self.v})"


class A:
    def __init__(self, flag: bool):
        if flag:
            self.w = 1


def describe(o):
    return hasattr(o, "__repr__"), hasattr(o, "__dict__"), hasattr(o, "v"), hasattr(o, "nope")


def kind(x):
    if hasattr(x, "keys"):
        return "mapping"
    if hasattr(x, "append"):
        return "list"
    if hasattr(x, "zfill"):
        return "str"
    return "other"


def has_w(o):
    return hasattr(o, "w")


def mk(i: int) -> C | None:
    return C(i) if i > 0 else None


def check(x):
    return isinstance(x, (C, str)), isinstance(x, int | float)


def head(s=None):
    return s and s[0]


def pick(s=None):
    return s or "default"


def add(item, acc=None):
    if acc is None:
        acc = []
    acc.append(item)
    return acc


def index(words, table=None):
    if table is None:
        table = {}
    for w in words:
        table[w] = len(w)
    return table


def find(xs, k):
    for x in xs:
        if x.v == k:
            return x


def make(x):
    if x > 0:
        return C(x)
    return


def size(x) -> int:
    if isinstance(x, str):
        return len(x)
    return x + 1


def inc(x=None):
    assert x is not None, "x required"
    return x + 1


def drain(x=None):
    n = 0
    while x:
        n += 1
        x = x[1:]
    return n


def collect(x):
    out = []
    if isinstance(x, bool):
        out.append(float(x))
    out.append(x)
    return out


def note(msg: str) -> None:
    print("note", msg)


def once(x, y=note("evaluated once")):
    return x


print(describe(C(1)), describe(None), hasattr(None, "__bool__"), hasattr(1, "bit_length"))
print(kind({"a": 1}), kind([1, 2]), kind("s"), kind(1.5))
print(has_w(A(True)), has_w(A(False)))
print(check(mk(1)), check(mk(0)), check("s"), check(2), check(2.5))
print(head(), head("xy"), pick(), pick("given"))
print(add(1), add("a", ["b"]), index(["ab", "c"]))
print(find([C(1), C(2)], 2), find([C(1)], 5) is None, make(3), make(0) is None)
print(size("abc"), size(4))
if len(sys.argv) > 5:
    print(inc())
print(inc(1), drain("abc"), drain(), collect(7))
print(once(1), once(2))
