# pystachy: dynamic-any
# CPython's exceptions, with its messages, for operations on Any values that their run-time
# types do not support.
from typing import Any


def attempt(label: str, a: Any, b: Any, op: str) -> None:
    try:
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            r = a / b
        elif op == "//":
            r = a // b
        elif op == "%":
            r = a % b
        elif op == "<":
            r = a < b
        elif op == "[]":
            r = a[b]
        elif op == "in":
            r = b in a
        elif op == "hash":
            r = hash(a)
        elif op == "len":
            r = len(a)
        elif op == "attr":
            r = a.missing
        elif op == "call":
            r = a.nomethod(b)
        elif op == "int":
            r = int(a)
        elif op == "neg":
            r = -a
        else:
            r = None
        print(label, "->", repr(r))
    except Exception as e:
        print(label, "raised", type(e).__name__ + ":", e)


attempt("int+str", 1, "a", "+")
attempt("str+int", "a", 1, "+")
attempt("list+str", [1], "a", "+")
attempt("tuple+list", (1,), [1], "+")
attempt("str-str", "a", "b", "-")
attempt("str*str", "a", "b", "*")
attempt("list*float", [1], 1.5, "*")
attempt("div0", 1, 0, "/")
attempt("fdiv0", 1.5, 0, "/")
attempt("floordiv0", 1, 0, "//")
attempt("mod0", 1, 0, "%")
attempt("int<str", 1, "a", "<")
attempt("list<tuple", [1], (1,), "<")
attempt("None<None", None, None, "<")
attempt("idx", [1, 2], 5, "[]")
attempt("negidx", [1, 2], -1, "[]")
attempt("stridx", "ab", 1, "[]")
attempt("strstridx", "ab", "x", "[]")
attempt("listkey", [1, 2], "x", "[]")
attempt("dictkey", {"a": 1}, "b", "[]")
attempt("tupleidx", (1, 2), 9, "[]")
attempt("intidx", 5, 0, "[]")
attempt("in int", 5, 1, "in")
attempt("in str int", "abc", 1, "in")
attempt("in str", "abc", "b", "in")
attempt("hash list", [1], None, "hash")
attempt("hash tuple", (1, 2.0, None), None, "hash")
attempt("len int", 5, None, "len")
attempt("attr", 5, None, "attr")
attempt("method", "s", 1, "call")
attempt("int str", "12", None, "int")
attempt("int bad", "x1", None, "int")
attempt("int list", [1], None, "int")
attempt("neg str", "s", None, "neg")
d: dict[Any, Any] = {}
try:
    d[[1, 2]] = 3
except TypeError as e:
    print("TypeError", e)
x: Any = [1, 2, 3]
try:
    a, b = x
except ValueError as e:
    print("ValueError", e)
try:
    a, b, c, dd = x
except ValueError as e:
    print("ValueError", e)
y: Any = 5
try:
    for item in y:
        print(item)
except TypeError as e:
    print("TypeError", e)
try:
    y[0] = 1
except TypeError as e:
    print("TypeError", e)
t: Any = (1, 2)
try:
    t[0] = 1
except TypeError as e:
    print("TypeError", e)
try:
    del t[0]
except TypeError as e:
    print("TypeError", e)
