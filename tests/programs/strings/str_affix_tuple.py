# str.startswith() and str.endswith() of a tuple of str: True if any item matches, in order,
# with the optional start and end; an empty tuple gives False
import sys
from typing import NamedTuple


def pick(t: tuple[str, str]) -> tuple[str, str]:
    print("tuple evaluated")
    return t


def at(i: int) -> int:
    print("index evaluated", i)
    return i


s = "hello.py"
print(s.startswith(("he", "x")), s.startswith(("x", "y")), s.endswith((".py", ".pyi")), s.endswith((".c",)))
print(s.startswith(()), s.endswith(()), "".startswith(()), "".startswith(("",)), "".endswith(("x", "")))
exts = (".txt", ".py", ".md")
for name in ["a.txt", "b.py", "c.rs", "", ".md"]:
    print(repr(name), name.endswith(exts), name.startswith(exts))
print([f for f in ["x.py", "y.c", "z.md"] if f.endswith(exts)])
# start and end, also negative, None, a bool and past the end
print(s.startswith(("ll", "el"), 1), s.startswith(("ll", "zz"), 2, 4), s.startswith(("llo",), 2, 4))
print(s.endswith(("lo", "x"), 0, 5), s.endswith(("lo",), None, -3), s.endswith(("o", "h"), -10, 1))
print(s.startswith(("", "x"), 8), s.startswith(("",), 9), s.endswith(("",), 3, 2), s.startswith(("py",), -2))
print(s.startswith(("e",), True), s.startswith(("h",), True), s.endswith(("h",), None, True))
big = 9223372036854775807
print(s.startswith(("",), big), s.startswith(("h", "x"), -big - 1, big), s.endswith(("",), 0, -big - 1))
# non-ASCII items, and a match at the last of many
print("héllo 😀".startswith(("hé", "x")), "😀x".startswith(("x", "\U0001F600")), "e\u0301".startswith(("é",)))
print("f.z".endswith((".a", ".b", ".c", ".d", ".e", ".f", ".g", ".h", ".i", ".j", ".k", ".z")))
# everything is evaluated once, in order, before the first item is tried
print(s.startswith(pick(("x", "hel")), at(0), at(100)))
print(s.endswith(pick(("p", "y")), at(-3)))
# items and tuples that may be None
q: str | None = "hel"
t2: tuple[str | None, str] = (q, "zz")
print(s.startswith(t2), s.startswith((None if len(s) > 100 else "q", "h")))
q = None
t2 = (q, "he")
print(s.startswith(("he", q)), s.endswith((".py", q)))
u: tuple[str, str] | None = ("x", "o.py")
print(s.endswith(u))


def receiver(r: str | None) -> None:
    if r is not None:
        print(r.startswith(("a", "b")), r.endswith(("a", "b")))
    try:
        print(r.startswith(pick(("a", "b"))))
    except AttributeError as e:
        print("AttributeError:", e)


receiver("abc")
receiver(None)


def tries(r: str, t: tuple[str | None, str], u: tuple[str, str] | None) -> None:
    try:
        print(r.startswith(t))
    except TypeError as e:
        print("TypeError:", e)
    try:
        print(r.endswith(t, 1))
    except TypeError as e:
        print("TypeError:", e)
    try:
        print(r.startswith(u, at(1)))
    except TypeError as e:
        print("TypeError:", e)
    try:
        print(r.endswith(u))
    except TypeError as e:
        print("TypeError:", e)


tries("abc", ("a", "b"), ("a", "c"))
tries("abc", (None, "b"), None)


# a NamedTuple is a tuple of its fields
class Pre(NamedTuple):
    a: str
    b: str | None


print(s.startswith(Pre("x", "he")), s.endswith(Pre("lo", None), 0, 5), s.endswith(Pre("py", "x"), at(-3)))
p: Pre | None = None
try:
    print(s.startswith(p, at(1)))
except TypeError as e:
    print("TypeError:", e)
try:
    print(s.startswith(Pre("x", None)))
except TypeError as e:
    print("TypeError:", e)
# a test of the platform with a tuple of Windows prefixes is decided at compile time, as with one
if sys.platform.startswith(("win", "cygwin")):
    import msvcrt

    print(msvcrt.getch())
print(sys.platform.startswith(("win", "cygwin")), sys.platform.startswith(()))
print(s.startswith(t2))
