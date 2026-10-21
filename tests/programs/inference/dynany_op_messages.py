# pystachy: dynamic-any
# The TypeError of an arithmetic operator that its Any operands' run-time types do not support
# names the operator as CPython does (#798): an in-place operator by its own symbol (+=, **=),
# ** as "** or pow()". Also for annotated targets of a typed type with an Any operand, for
# attribute and item targets, for pow() and for objects without the dunders.
from typing import Any

OPS = ["+", "-", "*", "/", "//", "%", "**", "<<", ">>", "&", "|", "^"]


class Plain:
    pass


class Holder:
    def __init__(self, v: Any) -> None:
        self.v = v


class Counter:
    def __init__(self) -> None:
        self.n: int = 1


def binary(a: Any, b: Any, op: str) -> Any:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b
    if op == "//":
        return a // b
    if op == "%":
        return a % b
    if op == "**":
        return a ** b
    if op == "<<":
        return a << b
    if op == ">>":
        return a >> b
    if op == "&":
        return a & b
    if op == "|":
        return a | b
    return a ^ b


def inplace(a: Any, b: Any, op: str) -> Any:
    r = a
    if op == "+":
        r += b
    elif op == "-":
        r -= b
    elif op == "*":
        r *= b
    elif op == "/":
        r /= b
    elif op == "//":
        r //= b
    elif op == "%":
        r %= b
    elif op == "**":
        r **= b
    elif op == "<<":
        r <<= b
    elif op == ">>":
        r >>= b
    elif op == "&":
        r &= b
    elif op == "|":
        r |= b
    else:
        r ^= b
    return r


def attempt(label: str, a: Any, b: Any) -> None:
    for op in OPS:
        try:
            print(label, op, repr(binary(a, b, op)))
        except TypeError as e:
            print(label, op, e)
        try:
            print(label, op + "=", repr(inplace(a, b, op)))
        except TypeError as e:
            print(label, op + "=", e)


def typed_targets(s: Any) -> None:
    x: int = 1
    try:
        x += s
    except TypeError as e:
        print("int +=", e)
    f: float = 1.5
    try:
        f **= s
    except TypeError as e:
        print("float **=", e)
    c = Counter()
    try:
        c.n -= s
    except TypeError as e:
        print("int field -=", e)
    xs: list[int] = [1]
    try:
        xs[0] //= s
    except TypeError as e:
        print("int item //=", e)
    print(x, f, c.n, xs)


def targets(a: Any, s: Any) -> None:
    h = Holder(a)
    try:
        h.v += s
    except TypeError as e:
        print("attribute +=", e)
    xs: list[Any] = [a]
    try:
        xs[0] //= s
    except TypeError as e:
        print("item //=", e)
    d: dict[str, Any] = {"k": a}
    try:
        d["k"] ^= s
    except TypeError as e:
        print("dict item ^=", e)
    try:
        print(pow(a, s))
    except TypeError as e:
        print("pow()", e)
    print(h.v, xs, d)


attempt("None, int:", None, 1)
attempt("int, None:", 1, None)
attempt("Plain, int:", Plain(), 1)
attempt("int, Plain:", 1, Plain())
attempt("list, str:", [1], "x")
typed_targets("z")
typed_targets(None)
targets(1, "z")
